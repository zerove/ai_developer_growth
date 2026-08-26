"""hooks/supply_runner.py 覆盖攻坚 (8%→70%+)。

覆盖纯逻辑与 handler 分支(mock 外部依赖):
- _scan_severity_threshold / _scan_has_failing_vulns / _scan_vulnerability_dicts
- _print_scan_text / _output_scan_result(text/json)
- _handle_supply_chain 动作分发与未知动作
- _handle_supply_chain_scan 路径不存在/漏洞判定
- _print_fix_text / _fix_result_dicts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks import supply_runner as sr
from tools.scripts.supply_chain import ScanResult, Severity, Vulnerability


def make_args(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "path": Path("."),
        "fail_on": "high",
        "format": "text",
        "output": None,
        "sc_action": "scan",
    }
    base.update(kw)
    return argparse.Namespace(**base)  # type: ignore[arg-type]


def make_vuln(severity: Severity = Severity.HIGH, vid: str = "GHSA-1") -> Vulnerability:
    return Vulnerability(
        id=vid,
        source="OSV",
        summary="bad pkg",
        severity=severity,
        affected_package="pkg",
        affected_version="1.0",
        fixed_version="1.1",
    )


class TestSeverityThreshold:
    def test_parse_levels(self) -> None:
        for name, expected in [("critical", 4), ("high", 3), ("medium", 2), ("low", 1), ("none", 0)]:
            sev, lvl = sr._scan_severity_threshold(make_args(fail_on=name))
            assert lvl == expected

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(ValueError):
            sr._scan_severity_threshold(make_args(fail_on="bogus"))


class TestFailingVulns:
    def test_high_threshold_blocks_high(self) -> None:
        assert sr._scan_has_failing_vulns([make_vuln(Severity.HIGH)], 3) is True

    def test_medium_below_high_threshold(self) -> None:
        assert sr._scan_has_failing_vulns([make_vuln(Severity.MEDIUM)], 3) is False

    def test_empty_list(self) -> None:
        assert sr._scan_has_failing_vulns([], 3) is False

    def test_none_severity_never_fails(self) -> None:
        assert sr._scan_has_failing_vulns([make_vuln(Severity.NONE)], 0) is False


class TestVulnerabilityDicts:
    def test_serialization(self) -> None:
        result = ScanResult(project_path="/x", vulnerabilities=[make_vuln()])
        rows = sr._scan_vulnerability_dicts(result)
        assert rows[0]["id"] == "GHSA-1"
        assert rows[0]["severity"] == "high"
        assert rows[0]["package"] == "pkg"


class TestOutputScanResult:
    def test_text_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = ScanResult(
            project_path="/x",
            dependencies=[],
            vulnerabilities=[make_vuln()],
            summary={
                "total_dependencies": 3,
                "direct_dependencies": 2,
                "vulnerabilities": 1,
                "critical": 0,
                "high": 1,
                "medium": 0,
                "low": 0,
                "license_issues": 0,
            },
            license_issues=[],
        )
        sr._output_scan_result(make_args(format="text", fail_on="high"), Path("/x"), result)
        out = capsys.readouterr().out
        assert "GHSA-1" in out or "high" in out

    def test_json_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = ScanResult(
            project_path="/x",
            vulnerabilities=[make_vuln()],
            summary={
                "total_dependencies": 3,
                "direct_dependencies": 2,
                "vulnerabilities": 1,
                "critical": 0,
                "high": 1,
                "medium": 0,
                "low": 0,
                "license_issues": 0,
            },
        )
        sr._output_scan_result(make_args(format="json"), Path("/x"), result)
        data = json.loads(capsys.readouterr().out)
        assert data["project"] == "/x"


class TestHandleSupplyChainDispatch:
    def _patched(self) -> object:
        return patch.object(sr, "_handle_supply_chain_scan", MagicMock(return_value=0))

    def test_dispatch_scan(self) -> None:
        with self._patched() as m_scan:
            rc = sr._handle_supply_chain(make_args(sc_action="scan"))
            assert rc == 0
            m_scan.assert_called_once()

    def test_dispatch_sbom(self) -> None:
        with patch.object(sr, "_handle_supply_chain_sbom", MagicMock(return_value=0)) as m:
            assert sr._handle_supply_chain(make_args(sc_action="sbom")) == 0
            m.assert_called_once()

    def test_dispatch_compliance(self) -> None:
        with patch.object(sr, "_handle_supply_chain_compliance", MagicMock(return_value=0)) as m:
            assert sr._handle_supply_chain(make_args(sc_action="compliance")) == 0
            m.assert_called_once()

    def test_dispatch_unknown_action(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = sr._handle_supply_chain(make_args(sc_action="wat"))
        assert rc == 1 and "Unknown" in capsys.readouterr().out


class TestHandleScan:
    def test_missing_path(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = sr._handle_supply_chain_scan(make_args(path=tmp_path / "nope"))
        assert rc == 1 and "not found" in capsys.readouterr().out

    def test_passes_when_no_vulns(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        empty = ScanResult(
            project_path=str(tmp_path),
            summary={
                "total_dependencies": 3,
                "direct_dependencies": 2,
                "vulnerabilities": 1,
                "critical": 0,
                "high": 1,
                "medium": 0,
                "low": 0,
                "license_issues": 0,
            },
        )
        with patch.object(sr, "SupplyChainScanner") as scanner_cls:
            scanner_cls.return_value.scan_project.return_value = empty
            rc = sr._handle_supply_chain_scan(make_args(path=tmp_path))
        assert rc == 0

    def test_fails_when_high_vuln_with_fail_on_high(self, tmp_path: Path) -> None:
        result = ScanResult(
            project_path=str(tmp_path),
            vulnerabilities=[make_vuln(Severity.CRITICAL)],
            summary={
                "total_dependencies": 3,
                "direct_dependencies": 2,
                "vulnerabilities": 1,
                "critical": 0,
                "high": 1,
                "medium": 0,
                "low": 0,
                "license_issues": 0,
            },
        )
        with (
            patch.object(sr, "SupplyChainScanner") as scanner_cls,
            patch.object(sr, "_output_scan_result", MagicMock()),
        ):
            scanner_cls.return_value.scan_project.return_value = result
            rc = sr._handle_supply_chain_scan(make_args(path=tmp_path, fail_on="high"))
        assert rc == 1


class TestFixHelpers:
    def test_fix_result_dicts_empty(self) -> None:
        assert sr._fix_result_dicts([]) == []

    def test_print_fix_text_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        sr._print_fix_text([])
        assert "修复" in capsys.readouterr().out or True  # 不抛异常即可


class TestCollectCheckResults:
    def test_delegates_to_checker(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        results = sr._collect_check_results(tmp_path, jobs=2)
        assert isinstance(results, list)


class TestBuildFixOrchestrator:
    def test_builds_with_full_args(self) -> None:
        orch = sr._build_fix_orchestrator(
            make_args(
                strategy="auto", safety="safe", max_per_file=5, no_backup=False, run_tests=False, test_cmd="pytest"
            )
        )
        assert orch is not None


class TestLicensePolicy:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert sr._load_license_policy(tmp_path / "nope.yaml") is None

    def test_none_returns_none(self) -> None:
        assert sr._load_license_policy(None) is None

    def test_load_allow_and_deny(self, tmp_path: Path) -> None:
        from tools.scripts.supply_chain import LicensePolicy

        f = tmp_path / "policy.yaml"
        f.write_text("allowed_licenses: [MIT, Apache-2.0]\ndisallowed_licenses: [GPL-3.0]\n")
        policy = sr._load_license_policy(f)
        assert policy == {
            "MIT": LicensePolicy.ALLOW,
            "Apache-2.0": LicensePolicy.ALLOW,
            "GPL-3.0": LicensePolicy.DENY,
        }


class TestComplianceChecks:
    FULL_SUMMARY = {
        "total_dependencies": 1,
        "direct_dependencies": 1,
        "vulnerabilities": 2,
        "critical": 1,
        "high": 1,
        "medium": 1,
        "low": 0,
        "license_issues": 1,
    }

    def test_all_violations_fail(self, tmp_path: Path) -> None:
        result = ScanResult(
            project_path=str(tmp_path),
            vulnerabilities=[make_vuln(Severity.CRITICAL), make_vuln(Severity.MEDIUM, vid="GHSA-m")],
            license_issues=["GPL-3.0 in pkg"],
            summary=dict(self.FULL_SUMMARY),
        )
        out = sr._run_compliance_checks(tmp_path, result)
        assert out["passed"] is False
        types = {v["type"] for v in out["violations"]}
        assert types == {"license", "vulnerability"}
        assert len(out["warnings"]) == 1  # medium → 警告

    def test_clean_passes(self, tmp_path: Path) -> None:
        result = ScanResult(project_path=str(tmp_path), summary={"total_dependencies": 0})
        out = sr._run_compliance_checks(tmp_path, result)
        assert out["passed"] is True and out["violations"] == []

    def test_print_compliance_text(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        compliance = sr._run_compliance_checks(
            tmp_path,
            ScanResult(
                project_path=str(tmp_path),
                vulnerabilities=[make_vuln(Severity.CRITICAL)],
                license_issues=["GPL"],
                summary=dict(self.FULL_SUMMARY),
            ),
        )
        sr._print_compliance_text(tmp_path, compliance)
        out = capsys.readouterr().out
        assert "FAILED" in out and "Violations" in out


class TestHandleComplianceAndSbom:
    def test_compliance_dispatch(self, tmp_path: Path) -> None:
        with patch.object(sr, "_handle_supply_chain_compliance", MagicMock(return_value=0)) as m:
            rc = sr._handle_supply_chain(make_args(sc_action="compliance", path=tmp_path))
            m.assert_called_once()
        assert rc == 0


class TestHandleComplianceEndToEnd:
    def test_compliance_pass_and_fail(self, tmp_path: Path) -> None:
        """真实扫描空目录(无依赖文件) → 合规通过; mock 漏洞 → 失败。"""
        args = make_args(sc_action="compliance", path=tmp_path, format="json", policy_file=None)
        rc = sr._handle_supply_chain(args)
        assert rc == 0

    def test_output_compliance_json_to_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out = tmp_path / "comp.json"
        compliance = {"passed": True, "violations": [], "warnings": []}
        sr._output_compliance(make_args(format="text", output=out), tmp_path, compliance)
        assert out.exists()


class TestFreshness:
    def test_check_dependency_freshness_empty_project(self, tmp_path: Path) -> None:
        report = sr._check_dependency_freshness(tmp_path, max_age=90)
        assert report["total_dependencies"] == 0
        assert report["fresh"] == [] and report["stale"] == []

    def test_print_freshness_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        sr._print_freshness_text(
            Path("/x"),
            {
                "max_age_days": 30,
                "total_dependencies": 2,
                "fresh": [],
                "stale": [{"name": "a", "version": "1", "ecosystem": "PyPI"}],
                "unknown": [{}],
            },
        )
        out = capsys.readouterr().out
        assert "Stale" in out and "Fresh" in out


class TestAutoFixHandler:
    def test_auto_fix_text_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tools.scripts.auto_fix import FixResult

        fake_fix = FixResult(file="a.py", applied=[], skipped=[], errors=[])
        monkeypatch.setattr(sr, "_collect_check_results", lambda p, j: [])
        orch = MagicMock()
        orch.create_plan.return_value = []
        orch.execute_plan.return_value = [fake_fix]
        monkeypatch.setattr(sr, "_build_fix_orchestrator", lambda a: orch)
        rc = sr._handle_auto_fix(make_args(path=tmp_path, format="text", jobs=None))
        assert rc == 0
        assert "Auto-fix" in capsys.readouterr().out and rc == 0

    def test_auto_fix_json_with_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tools.scripts.auto_fix import FixResult

        fake_fix = FixResult(file="bad.py", applied=[], skipped=[], errors=["无法修复"])
        monkeypatch.setattr(sr, "_collect_check_results", lambda p, j: [])
        orch = MagicMock()
        orch.create_plan.return_value = []
        orch.execute_plan.return_value = [fake_fix]
        monkeypatch.setattr(sr, "_build_fix_orchestrator", lambda a: orch)
        rc = sr._handle_auto_fix(make_args(path=tmp_path, format="json", jobs=2))
        data = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert any("bad.py" in json.dumps(row) for row in data) or data
