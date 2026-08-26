"""quality_gate.py 覆盖攻坚 (17%→80%+)。

覆盖:
- GateResult / QualityGateReport 的 to_dict / to_sarif
- BaselineManager: load/save/update/compare 全语义(新增/修复/恶化/改善/不变)
- ExceptionManager: add/remove/get_active/is_excepted/apply_exceptions(含过期)
- QualityGateEngine.evaluate: 各门禁规则分支
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts.config.models import (
    BaselineConfig,
    ExceptionRule,
    GovernanceConfig,
    QualityGateConfig,
    SeverityLevel,
)
from tools.scripts.quality_gate import (
    BaselineManager,
    ExceptionManager,
    GateResult,
    QualityGateEngine,
    QualityGateReport,
)
from tools.scripts.rules_engine.models import CheckResult, Issue


def make_result(
    file: str = "a.py",
    rule_id: str = "R1",
    line: int = 1,
    column: int = 0,
    severity: str = "warning",
    message: str = "msg",
) -> CheckResult:
    return CheckResult(
        file=file,
        issues=[
            Issue(
                rule_id=rule_id,
                severity=severity,
                category="style",
                file=file,
                line=line,
                column=column,
                message=message,
            )
        ],
    )


def make_manager(tmp_path: Path) -> BaselineManager:
    cfg = BaselineConfig(enabled=True, path=str(tmp_path / "baseline.json"))
    return BaselineManager(cfg)


class TestGateReportSerialization:
    def test_to_dict(self) -> None:
        r = GateResult(gate_name="g", passed=False, rule_id="x", message="m", details={"k": 1})
        report = QualityGateReport(gate_name="g", overall_passed=False, results=[r])
        d = report.to_dict()
        assert d["gate_name"] == "g"
        assert d["overall_passed"] is False
        assert d["results"][0]["severity"] == SeverityLevel.ERROR.value

    def test_to_sarif_only_failures(self) -> None:
        ok = GateResult(gate_name="g", passed=True, rule_id="ok", message="fine")
        bad = GateResult(gate_name="g", passed=False, rule_id="bad", message="broken")
        report = QualityGateReport(gate_name="g", overall_passed=False, results=[ok, bad])
        sarif = report.to_sarif()
        ids = [r["ruleId"] for r in sarif["runs"][0]["results"]]
        assert ids == ["bad"]
        assert sarif["version"] == "2.1.0"


class TestBaselineManager:
    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        assert make_manager(tmp_path).load_baseline() == {}

    def test_load_corrupt_returns_empty(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.baseline_path.write_text("{not json")
        assert m.load_baseline() == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.save_baseline({"version": 1, "files": {}})
        assert json.loads(m.baseline_path.read_text())["version"] == 1

    def test_update_baseline_from_results(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        baseline = m.update_baseline([make_result()])
        keys = list(baseline["files"]["a.py"].keys())
        assert keys == ["R1:1:0"]

    def test_compare_new_issue(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.update_baseline([])  # 空基线
        cmp = m.compare_with_baseline([make_result()])
        assert cmp["summary"]["new_count"] == 1
        assert cmp["new"][0]["rule_id"] == "R1"

    def test_compare_fixed_issue(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.update_baseline([make_result()])
        cmp = m.compare_with_baseline([])
        assert cmp["summary"]["fixed_count"] == 1

    def test_compare_unchanged(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.update_baseline([make_result(severity="error")])
        cmp = m.compare_with_baseline([make_result(severity="error")])
        assert len(cmp["unchanged"]) == 1

    def test_compare_worsened(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.update_baseline([make_result(severity="info")])
        cmp = m.compare_with_baseline([make_result(severity="error")])
        assert cmp["summary"]["worsened_count"] == 1

    def test_compare_improved(self, tmp_path: Path) -> None:
        m = make_manager(tmp_path)
        m.update_baseline([make_result(severity="error")])
        cmp = m.compare_with_baseline([make_result(severity="info")])
        assert cmp["summary"]["improved_count"] == 1

    def test_compare_empty_baseline(self, tmp_path: Path) -> None:
        """无基线文件时 compare 直接按空基线处理。"""
        m = make_manager(tmp_path)
        cmp = m.compare_with_baseline([make_result()])
        assert cmp["summary"]["new_count"] == 1


class TestExceptionManager:
    def _mgr(self, exceptions: list[ExceptionRule] | None = None) -> ExceptionManager:
        cfg = GovernanceConfig(exceptions=exceptions or [])
        return ExceptionManager(cfg)

    def test_add_and_remove(self) -> None:
        m = self._mgr()
        exc = m.add_exception("R9", ["legacy/*"], reason="历史遗留")
        assert exc.id and m.remove_exception(exc.id) is True
        assert m.remove_exception("no-such-id") is False

    def test_get_active_filters_by_rule(self) -> None:
        m = self._mgr()
        m.add_exception("RA", ["*"], reason="a")
        m.add_exception("RB", ["*"], reason="b")
        active = m.get_active_exceptions(rule_id="RA")
        assert len(active) == 1 and active[0].rule == "RA"

    def test_expired_exception_not_active(self) -> None:
        m = self._mgr()
        m.add_exception("R1", ["*"], reason="过期", expires="2000-01-01T00:00:00")
        assert m.get_active_exceptions() == []

    def test_bad_expiry_format_stays_active(self) -> None:
        m = self._mgr()
        m.add_exception("R1", ["*"], reason="坏格式", expires="not-a-date")
        assert len(m.get_active_exceptions()) == 1

    def test_is_excepted_glob_match(self) -> None:
        m = self._mgr()
        m.add_exception("R1", ["tests/*", "demo/*.py"], reason="测试豁免")
        assert m.is_excepted("tests/x.py", "R1") is not None
        assert m.is_excepted("src/x.py", "R1") is None
        assert m.is_excepted("src/x.py", "R2") is None

    def test_apply_exceptions_downgrade_and_skip(self) -> None:
        m = self._mgr()
        # INFO → 完全忽略; WARNING → 降级标记
        m.add_exception("R_INFO", ["*"], reason="忽略", severity=SeverityLevel.INFO)
        m.add_exception("R_WARN", ["*"], reason="降级", severity=SeverityLevel.WARNING)
        results = [
            make_result(file="i.py", rule_id="R_INFO"),
            make_result(file="w.py", rule_id="R_WARN"),
            make_result(file="keep.py", rule_id="R_KEEP"),
        ]
        out = m.apply_exceptions(results)
        by_file = {r.file: r for r in out}
        assert by_file["i.py"].issues == []
        assert by_file["w.py"].issues[0].message.startswith("[EXCEPTED]")
        assert by_file["keep.py"].issues[0].message == "msg"


def make_engine(tmp_path: Path, gate_overrides: dict | None = None, baseline_enabled: bool = True) -> QualityGateEngine:
    from tools.scripts.config import get_config as _orig  # noqa: F401  仅示意

    gov = GovernanceConfig()
    gov.baseline = BaselineConfig(enabled=baseline_enabled, path=str(tmp_path / "baseline.json"), fail_on_worsened=True)
    if gate_overrides:
        gov.quality_gates["default"] = QualityGateConfig(name="default", **gate_overrides)
    engine = QualityGateEngine(gov)
    return engine


class TestQualityGateEngineEvaluate:
    def test_clean_results_pass(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        report = engine.evaluate([], baseline={"files": {}})
        assert report.overall_passed is True

    def test_current_error_fails_gate(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        report = engine.evaluate([make_result(severity="error")], baseline={"files": {}})
        current = [r for r in report.results if r.rule_id == "gate.current-errors"]
        assert current[0].passed is False
        assert report.overall_passed is False

    def test_zero_new_errors_rule_triggers(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path, {"require_zero_new_errors": True})
        base = engine.baseline_manager.update_baseline([])
        report = engine.evaluate([make_result(rule_id="NEW_R", severity="error")], baseline=base)
        zero_err = [r for r in report.results if r.rule_id == "gate.zero-new-errors"]
        assert zero_err[0].passed is False

    def test_max_new_errors_within_limit(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path, {"max_new_errors": 5})
        base = engine.baseline_manager.update_baseline([])
        report = engine.evaluate([make_result(rule_id="NEW_R", severity="error")], baseline=base)
        max_err = [r for r in report.results if r.rule_id == "gate.max-new-errors"]
        assert max_err[0].passed is True

    def test_zero_new_warnings_disabled_by_default(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path, {"require_zero_new_warnings": False})
        base = engine.baseline_manager.update_baseline([])
        report = engine.evaluate([make_result(severity="warning")], baseline=base)
        assert all(r.rule_id != "gate.zero-new-warnings" for r in report.results)

    def test_worsened_fails_when_configured(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path, baseline_enabled=True)
        base = engine.baseline_manager.update_baseline([make_result(severity="info")])
        report = engine.evaluate([make_result(severity="error")], baseline=base)
        worsened = [r for r in report.results if r.rule_id == "gate.no-worsened"]
        assert worsened[0].passed is False

    def test_coverage_stub_passes(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path, {"min_coverage_overall": 80.0})
        report = engine.evaluate([], baseline={"files": {}})
        cov = [r for r in report.results if r.rule_id == "gate.coverage-overall"]
        assert cov[0].passed is True and "待实现" in cov[0].message

    def test_unknown_gate_uses_default_config(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        report = engine.evaluate([], gate_name="custom-gate", baseline={"files": {}})
        assert report.gate_name == "custom-gate"

    def test_baseline_disabled_skips_comparison(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path, baseline_enabled=False)
        report = engine.evaluate([make_result()], baseline=None)
        assert report.baseline_comparison is None

    def test_report_metadata(self, tmp_path: Path) -> None:
        import time

        engine = make_engine(tmp_path)
        time.sleep(0.01)
        report = engine.evaluate([], baseline={"files": {}})
        assert report.scan_duration_ms >= 0
        assert report.timestamp
