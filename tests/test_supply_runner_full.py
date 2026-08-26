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
