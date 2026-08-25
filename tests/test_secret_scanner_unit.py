"""secret_scanner 序列化与判定逻辑单元测试（改进建议 8）。"""

from __future__ import annotations

import json

from tools.scripts.secret_scanner import SecretFinding, SecretScanResult


def _finding(**kw: object) -> SecretFinding:
    base: dict[str, object] = {
        "tool": "gitleaks",
        "rule_id": "aws-access-token",
        "file": "src/config.py",
        "line": 42,
    }
    base.update(kw)
    return SecretFinding(**base)  # type: ignore[arg-type]


class TestSecretFindingSarif:
    def test_high_severity_maps_to_error(self) -> None:
        sarif = _finding(severity="high").to_sarif()
        assert sarif["level"] == "error"
        assert sarif["ruleId"] == "aws-access-token"
        assert sarif["locations"][0]["physicalLocation"]["region"]["startLine"] == 42

    def test_medium_severity_maps_to_warning(self) -> None:
        assert _finding(severity="medium").to_sarif()["level"] == "warning"

    def test_secret_preview_masked(self) -> None:
        sarif = _finding(secret="AKIAIOSFODNN7EXAMPLE").to_sarif()
        preview = sarif["properties"]["secretPreview"]
        assert preview == "AKIAIOSF..."
        assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(sarif)

    def test_empty_secret_preview_blank(self) -> None:
        assert _finding().to_sarif()["properties"]["secretPreview"] == ""

    def test_column_defaults_to_1(self) -> None:
        region = _finding().to_sarif()["locations"][0]["physicalLocation"]["region"]
        assert region["startColumn"] == 1


class TestSecretScanResult:
    def test_has_critical_and_high(self) -> None:
        result = SecretScanResult(findings=[_finding(severity="critical"), _finding(severity="high")])
        assert result.has_critical and result.has_high

    def test_no_findings_flags_false(self) -> None:
        result = SecretScanResult()
        assert not result.has_critical and not result.has_high

    def test_sarif_envelope(self) -> None:
        result = SecretScanResult(findings=[_finding()])
        sarif = result.to_sarif()
        assert sarif["version"] == "2.1.0"
        assert sarif["runs"][0]["tool"]["driver"]["name"] == "jcode-secret-scan"
        assert len(sarif["runs"][0]["results"]) == 1

    def test_to_json_roundtrip_fields(self) -> None:
        result = SecretScanResult(
            findings=[_finding()],
            scanned_files=10,
            scan_duration_ms=200,
            tools_used=["gitleaks"],
            errors=[],
        )
        data = json.loads(result.to_json())
        assert data["scanned_files"] == 10
        assert data["scan_duration_ms"] == 200
        assert data["tools_used"] == ["gitleaks"]
        assert len(data["findings"]) == 1
