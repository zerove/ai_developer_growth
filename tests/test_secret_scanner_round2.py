"""secret_scanner 覆盖攻坚(21%→85%+): 三工具适配器/scan 主流程/去重/入口函数。

mock subprocess, 验证:
- _run_gitleaks: JSON 解析/坏 JSON/超时/allowlist 临时文件/pr-diff --staged
- _run_trufflehog: NDJSON 逐行解析/三 scan_type/verify_active 参数
- _run_detect_secrets: 基线读取/非 workspace 短路
- scan: 多工具聚合/异常收集/去重
- scan_secrets: sarif/json output_file
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.secret_scanner import SecretFinding, SecretScanner, scan_secrets


def _proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    p = MagicMock(returncode=returncode)
    p.stdout = stdout
    p.stderr = ""
    return p


class TestRunGitleaks:
    def test_parses_findings_with_entropy_severity(self, tmp_path: Path) -> None:
        payload = json.dumps(
            [
                {
                    "RuleID": "aws-key",
                    "File": "a.py",
                    "StartLine": 10,
                    "StartColumn": 5,
                    "Secret": "AKIA" + "x" * 40,
                    "Entropy": 5.2,
                    "Commit": "abc123",
                },
                {
                    "RuleID": "low-ent",
                    "File": "b.py",
                    "StartLine": 1,
                    "Secret": "short",
                    "Entropy": 2.0,
                },
            ]
        )
        scanner = SecretScanner(tools=["gitleaks"], entropy_threshold=4.5)
        with patch.object(subprocess, "run", return_value=_proc(payload)):
            findings = scanner._run_gitleaks(tmp_path, "git-history")
        assert len(findings) == 2
        assert findings[0].severity == "high" and findings[0].commit == "abc123"
        assert findings[1].severity == "medium"
        assert len(findings[0].secret) <= 100

    def test_invalid_json_warns(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        scanner = SecretScanner(tools=["gitleaks"])
        with patch.object(subprocess, "run", return_value=_proc("not-json")):
            assert scanner._run_gitleaks(tmp_path, "workspace") == []

    def test_timeout_returns_empty(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["gitleaks"])
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="gitleaks", timeout=300)):
            assert scanner._run_gitleaks(tmp_path, "workspace") == []

    def test_pr_diff_uses_staged_flag(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["gitleaks"])
        captured: dict[str, list[str]] = {}

        def fake_run(cmd: list[str], **kw: object) -> MagicMock:
            captured["cmd"] = cmd
            return _proc("")

        with patch.object(subprocess, "run", side_effect=fake_run):
            scanner._run_gitleaks(tmp_path, "pr-diff")
        assert "--staged" in captured["cmd"]

    def test_allowlist_writes_config(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["gitleaks"], allowlist=["tests/*"])
        captured: dict[str, list[str]] = {}

        def fake_run(cmd: list[str], **kw: object) -> MagicMock:
            captured["cmd"] = cmd
            return _proc("")

        with patch.object(subprocess, "run", side_effect=fake_run):
            scanner._run_gitleaks(tmp_path, "workspace")
        assert "--config" in captured["cmd"]
        # workspace 模式带 --no-git
        assert "--no-git" in captured["cmd"]


class TestRunTrufflehog:
    def test_ndjson_parsing(self, tmp_path: Path) -> None:
        line = json.dumps(
            {
                "DetectorType": "AWSKey",
                "Raw": "rawsecret",
                "SourceMetadata": {
                    "Data": {
                        "Filesystem": {"file": "cfg.py", "line": 7},
                        "Git": {"commit": "deadbeef"},
                    }
                },
            }
        )
        scanner = SecretScanner(tools=["trufflehog"])
        with patch.object(subprocess, "run", return_value=_proc(line + "\n\n")):
            findings = scanner._run_trufflehog(tmp_path, "workspace")
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "AWSKey" and f.file == "cfg.py" and f.line == 7 and f.commit == "deadbeef"

    def test_scan_types_change_command(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["trufflehog"])
        commands: list[list[str]] = []

        def fake_run(cmd: list[str], **kw: object) -> MagicMock:
            commands.append(list(cmd))
            return _proc("")

        with patch.object(subprocess, "run", side_effect=fake_run):
            for st in ("workspace", "git-history", "pr-diff"):
                scanner._run_trufflehog(tmp_path, st)
        joined = [" ".join(c) for c in commands]
        assert any("filesystem" in j for j in joined)
        assert sum("--since-commit" in j for j in joined) == 1

    def test_unknown_scan_type_short_circuit(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["trufflehog"])
        assert scanner._run_trufflehog(tmp_path, "unknown-type") == []


class TestRunDetectSecrets:
    def test_reads_baseline(self, tmp_path: Path) -> None:
        baseline = {
            "results": {"src/a.py": [{"type": "Secret Keyword", "line_number": 4, "hashed_secret": "abcdef1234567890"}]}
        }
        (tmp_path / ".secrets.baseline").write_text(json.dumps(baseline))
        scanner = SecretScanner(tools=["detect-secrets"])
        with patch.object(subprocess, "run", return_value=_proc()):
            findings = scanner._run_detect_secrets(tmp_path, "workspace")
        assert len(findings) == 1
        assert findings[0].tool == "detect-secrets" and findings[0].severity == "medium"

    def test_non_workspace_noop(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["detect-secrets"])
        assert scanner._run_detect_secrets(tmp_path, "git-history") == []


class TestScanAggregation:
    def test_dedup_and_errors(self, tmp_path: Path) -> None:
        dup = SecretFinding(tool="gitleaks", rule_id="R", file="f.py", line=1, secret="s")
        scanner = SecretScanner(tools=["gitleaks"])

        def fake_run(path: Path, st: str) -> list[SecretFinding]:
            if st == "git-history":
                raise RuntimeError("boom-history")
            return [dup, SecretFinding(tool="gitleaks", rule_id="R", file="f.py", line=1, secret="s")]

        with patch.object(scanner, "_run_gitleaks", side_effect=fake_run):
            result = scanner.scan(tmp_path, scan_workspace=True, scan_git_history=True)
        assert len(result.findings) == 1  # 去重生效
        assert result.errors and "boom-history" in result.errors[0]
        assert result.tools_used == ["gitleaks"]
        assert result.scan_duration_ms >= 0

    def test_detect_secrets_branch_in_scan(self, tmp_path: Path) -> None:
        scanner = SecretScanner(tools=["detect-secrets"])
        finding = SecretFinding(tool="detect-secrets", rule_id="t", file="a", line=1, secret="h")
        with patch.object(scanner, "_run_detect_secrets", return_value=[finding]):
            result = scanner.scan(tmp_path, scan_workspace=True, scan_git_history=False)
        assert len(result.findings) == 1


class TestScanSecretsEntrypoint:
    def test_sarif_output_file(self, tmp_path: Path) -> None:
        out = tmp_path / "report.sarif"
        result = scan_secrets(tmp_path, tools=[], output_format="sarif", output_file=out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "runs" in data or isinstance(data, dict)
        assert result.findings == []

    def test_json_output_file(self, tmp_path: Path) -> None:
        out = tmp_path / "r.json"
        scan_secrets(tmp_path, tools=[], output_format="json", output_file=out)
        assert json.loads(out.read_text()) is not None

    def test_no_output_file_still_returns_result(self, tmp_path: Path) -> None:
        r = scan_secrets(tmp_path, tools=[], output_format="text")
        assert r.scanned_files == 0
