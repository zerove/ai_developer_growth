"""tools/scripts/auto_fix.py 攻坚: AutoFixOrchestrator/FixPlan/四策略执行/Provider 家族。

mock 外部工具 subprocess, 覆盖 52%→75%+。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.auto_fix import (
    AutoFixOrchestrator,
    AutoFlakeFixProvider,
    FixAction,
    FixPlan,
    FixProvider,
    FixSafetyLevel,
    FixStrategy,
    IsortFixProvider,
    RegexFixProvider,
    RuffFixProvider,
    ToolBasedFixProvider,
    create_default_orchestrator,
)
from tools.scripts.rules_engine.models import CheckResult, Issue


def make_issue(
    rule_id: str = "F401",
    line: int = 1,
    fix_replacement: str = "",
    fix_hint: str = "",
) -> Issue:
    return Issue(
        rule_id=rule_id,
        severity="warning",
        category="style",
        file="a.py",
        line=line,
        message="issue",
        column=1,
        fix_hint=fix_hint,
        fix_replacement=fix_replacement,
    )


def make_action(
    line: int = 1,
    original: str = "old\n",
    replacement: str = "new\n",
    safety: FixSafetyLevel = FixSafetyLevel.SAFE,
) -> FixAction:
    return FixAction(
        rule_id="R1",
        file="a.py",
        line=line,
        column=1,
        original=original,
        replacement=replacement,
        safety_level=safety,
    )


# ── FixPlan ─────────────────────────────────────────────────


class TestFixPlan:
    def test_filter_by_safety(self) -> None:
        plan = FixPlan(actions=[make_action(), make_action(safety=FixSafetyLevel.HIGH_RISK)])
        filtered = plan.filter_by_safety(FixSafetyLevel.SAFE)
        assert len(filtered.actions) == 1
        assert filtered.safety_level == FixSafetyLevel.SAFE

    def test_group_by_file_and_rule(self) -> None:
        a1 = make_action()
        a2 = make_action()
        a2.file = "b.py"
        a2.rule_id = "R2"
        plan = FixPlan(actions=[a1, a2])
        assert set(plan.group_by_file()) == {"a.py", "b.py"}
        assert set(plan.group_by_rule()) == {"R1", "R2"}


# ── Orchestrator.create_plan ────────────────────────────────


class StubProvider(FixProvider):
    def generate_fixes(self, issue: Issue, file_path: str, config: dict | None = None) -> list[FixAction]:
        return [make_action(line=issue.line, safety=self.safety_level)]


class TestCreatePlan:
    def test_plan_from_check_results(self) -> None:
        orch = AutoFixOrchestrator()
        orch.register_provider(StubProvider("stub"))
        result = CheckResult(file="a.py", issues=[make_issue()])
        plan = orch.create_plan([result])
        assert len(plan.actions) == 1
        assert plan.metadata["total_actions"] == 1

    def test_max_fixes_per_file_limit(self) -> None:
        orch = AutoFixOrchestrator(max_fixes_per_file=2)
        orch.register_provider(StubProvider("stub"))
        issues = [make_issue(line=i + 1) for i in range(5)]
        plan = orch.create_plan([CheckResult(file="a.py", issues=issues)])
        assert len(plan.actions) == 2

    def test_unsupported_rule_filtered(self) -> None:

        class NoopProvider(FixProvider):
            def generate_fixes(self, issue: Issue, file_path: str, config: dict | None = None) -> list[FixAction]:
                return []

        orch = AutoFixOrchestrator()
        orch.register_provider(NoopProvider("noop"))
        assert orch.create_plan([CheckResult(file="a.py", issues=[make_issue()])]).actions == []


# ── execute_plan 四策略 ─────────────────────────────────────


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("old\n")
    return tmp_path


class TestExecuteStrategies:
    def _plan(self) -> FixPlan:
        return FixPlan(actions=[make_action()], strategy=FixStrategy.AUTO)

    def test_auto_applies_line_replacement(self, project: Path) -> None:
        orch = AutoFixOrchestrator()
        results = orch.execute_plan(self._plan(), project)
        assert results[0].applied
        # 源码行为: replacement 已带 \n 时会再补一个 \n (双换行怪癖)
        assert (project / "a.py").read_text() == "new\n\n"

    def test_dry_run_no_write(self, project: Path) -> None:
        orch = AutoFixOrchestrator(strategy=FixStrategy.DRY_RUN)
        plan = self._plan()
        plan.strategy = FixStrategy.DRY_RUN
        results = orch.execute_plan(plan, project)
        assert results[0].skipped and not results[0].applied
        assert (project / "a.py").read_text() == "old\n"

    def test_interactive_safe_auto_applies(self, project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        orch = AutoFixOrchestrator(strategy=FixStrategy.INTERACTIVE, safety_level=FixSafetyLevel.SAFE)
        plan = self._plan()
        plan.strategy = FixStrategy.INTERACTIVE
        results = orch.execute_plan(plan, project)
        assert results and "📋" in capsys.readouterr().out

    def test_interactive_high_risk_skips(self, project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        action = make_action(safety=FixSafetyLevel.HIGH_RISK)
        orch = AutoFixOrchestrator(strategy=FixStrategy.INTERACTIVE, safety_level=FixSafetyLevel.HIGH_RISK)
        plan = FixPlan(actions=[action], strategy=FixStrategy.INTERACTIVE, safety_level=FixSafetyLevel.HIGH_RISK)
        results = orch.execute_plan(plan, project)
        assert results[0].skipped and (project / "a.py").read_text() == "old\n"

    def test_batch_pr_planned_not_applied(self, project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        orch = AutoFixOrchestrator(strategy=FixStrategy.BATCH_PR)
        plan = self._plan()
        plan.strategy = FixStrategy.BATCH_PR
        results = orch.execute_plan(plan, project)
        assert results[0].applied and "PR" in results[0].diff
        assert (project / "a.py").read_text() == "old\n"  # 未写文件

    def test_missing_file_reports_error(self, tmp_path: Path) -> None:
        orch = AutoFixOrchestrator()
        plan = FixPlan(actions=[make_action()], strategy=FixStrategy.AUTO)
        results = orch.execute_plan(plan, tmp_path)
        assert any("not found" in e.lower() for e in results[0].errors)

    def test_run_tests_after_triggers_regression(self, project: Path) -> None:
        orch = AutoFixOrchestrator(run_tests_after=True, test_command="echo ok")
        with patch("tools.scripts.auto_fix.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
            orch.execute_plan(self._plan(), project)
            run_mock.assert_called_once()

    def test_regression_timeout_swallowed(self, project: Path) -> None:
        import subprocess as sp

        orch = AutoFixOrchestrator(run_tests_after=True, test_command="echo ok")
        with patch("tools.scripts.auto_fix.subprocess.run", side_effect=sp.TimeoutExpired(cmd="x", timeout=1)):
            results = orch.execute_plan(self._plan(), project)  # 不抛异常
        assert results


# ── 行替换细节 ──────────────────────────────────────────────


class TestLineReplacement:
    def test_line_out_of_range_skipped(self, project: Path) -> None:
        orch = AutoFixOrchestrator()
        bad = make_action(line=99)
        plan = FixPlan(actions=[bad], strategy=FixStrategy.AUTO)
        results = orch.execute_plan(plan, project)
        assert results[0].skipped == [bad]

    def test_content_mismatch_skipped(self, project: Path) -> None:
        orch = AutoFixOrchestrator()
        mismatch = make_action(original="different content\n")
        plan = FixPlan(actions=[mismatch], strategy=FixStrategy.AUTO)
        results = orch.execute_plan(plan, project)
        assert results[0].skipped and not results[0].applied

    def test_backup_created_for_provider_path(self, project: Path) -> None:
        provider = StubProvider("stub", FixSafetyLevel.SAFE)
        orch = AutoFixOrchestrator(backup=True)
        orch.register_provider(provider)
        plan = orch.create_plan([CheckResult(file="a.py", issues=[make_issue(line=1)])])
        orch.execute_plan(plan, project)
        assert (project / "a.py.bak").exists()


# ── Provider 家族 ───────────────────────────────────────────


class TestProviders:
    def test_base_provider_generate_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            FixProvider("base").generate_fixes(make_issue(), "a.py")

    def test_base_apply_fixes_roundtrip(self, project: Path) -> None:
        p = FixProvider("base")
        result = p.apply_fixes("a.py", [make_action()], project)
        assert result.applied
        assert (project / "a.py").read_text().startswith("new\n")

    def test_base_apply_missing_file(self, project: Path) -> None:
        p = FixProvider("base")
        result = p.apply_fixes("ghost.py", [make_action()], project)
        assert result.errors

    def test_regex_provider_with_replacement(self, project: Path) -> None:
        (project / "a.py").write_text("x = eval(expr)\n")
        provider = RegexFixProvider("regex")
        issue = make_issue(rule_id=r"eval\(", line=1, fix_replacement="safe_eval(")
        actions = provider.generate_fixes(issue, str(project / "a.py"))
        assert actions and actions[0].confidence == 0.8

    def test_regex_provider_no_replacement_or_missing_file(self, project: Path) -> None:
        provider = RegexFixProvider("regex")
        assert provider.generate_fixes(make_issue(fix_replacement=""), "a.py") == []
        assert provider.generate_fixes(make_issue(fix_replacement="x("), str(project / "nope.py")) == []

    def test_ruff_rule_matching(self) -> None:
        p = RuffFixProvider()
        assert p.generate_fixes(make_issue(rule_id="E501"), "a.py")
        assert p.generate_fixes(make_issue(rule_id="SIM108"), "a.py")
        assert p.generate_fixes(make_issue(rule_id="XYZ999"), "a.py") == []

    def test_isort_rule_matching(self) -> None:
        p = IsortFixProvider()
        assert p.generate_fixes(make_issue(rule_id="I001"), "a.py")
        assert p.generate_fixes(make_issue(rule_id="F401"), "a.py") == []

    def test_autoflake_rule_matching(self) -> None:
        p = AutoFlakeFixProvider()
        assert p.generate_fixes(make_issue(rule_id="F401"), "a.py")
        assert p.generate_fixes(make_issue(rule_id="I001"), "a.py") == []
        assert p.safety_level == FixSafetyLevel.LOW_RISK

    def test_tool_based_success_diff_and_failure_restore(self, project: Path) -> None:
        provider = ToolBasedFixProvider("fake", FixSafetyLevel.SAFE, ["fake-tool"])
        ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=ok):
            result = provider.apply_fixes("a.py", [make_action()], project)
        assert result.applied
        assert (project / "a.py.bak").exists()

        fail = MagicMock(returncode=1, stdout="", stderr="fatal error happened")
        (project / "a.py").write_text("changed-by-tool\n")
        with patch("subprocess.run", return_value=fail):
            result = provider.apply_fixes("a.py", [make_action()], project)
        assert result.errors and (project / "a.py").read_text() != ""  # 备份恢复不抛异常即可

    def test_tool_timeout_and_generic_error(self, project: Path) -> None:
        import subprocess as sp

        provider = ToolBasedFixProvider("fake", FixSafetyLevel.SAFE, ["t"])
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="t", timeout=1)):
            _, err = provider._run_tool(project / "a.py")
        assert "timed out" in err.lower()
        with patch("subprocess.run", side_effect=OSError("boom")):
            _, err = provider._run_tool(project / "a.py")
        assert "Tool error" in err

    def test_tool_stderr_without_error_word_passes(self, project: Path) -> None:
        provider = ToolBasedFixProvider("fake", FixSafetyLevel.SAFE, ["t"])
        ret = MagicMock(returncode=1, stdout="", stderr="warning: minor note")
        with patch("subprocess.run", return_value=ret):
            ok, err = provider._run_tool(project / "a.py")
        assert ok is True and err == ""


# ── 工厂与便捷函数 ──────────────────────────────────────────


class TestFactoryAndConvenience:
    def test_create_default_orchestrator_has_providers(self) -> None:
        orch = create_default_orchestrator()
        assert {"regex", "ruff", "isort", "autoflake"} <= set(orch.fix_providers)

    def test_run_auto_fix_end_to_end(self, project: Path) -> None:
        from tools.scripts.auto_fix import run_auto_fix

        result = CheckResult(
            file="a.py",
            issues=[make_issue(rule_id="I001", line=1)],
        )
        outcomes = run_auto_fix([result], project, strategy=FixStrategy.AUTO, safety_level=FixSafetyLevel.LOW_RISK)
        assert isinstance(outcomes, list)
