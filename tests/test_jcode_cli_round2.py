"""jcode_cli 第二轮攻坚: 11 个 cmd_* 处理器 + main 异常分支。

全部走进程内调用(mock 重依赖), 覆盖 13%→70%+:
- cmd_ai_quality_gate(verbose/有 issues/干净)
- cmd_ai_pr_review(无变更/有问题/干净)
- cmd_case_quality(单案例/全量)
- cmd_validate_case_study / create_case_study(argv 转发)
- cmd_dor_check(pass/fail)
- cmd_semantic_graph(query/无 query)
- cmd_arch_visualizer / metrics_telemetry / audit_attestation
- cmd_ai_native_workflow
- main(无命令/help/KeyboardInterrupt/异常)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts import jcode_cli


def _args(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {"verbose": False, "intent": None, "path": None, "rest": []}
    base.update(kw)
    return argparse.Namespace(**base)  # type: ignore[arg-type]


class TestAiQualityGate:
    def test_clean(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = MagicMock(issues=[])
        with patch("tools.scripts.rules_engine.check_directory", return_value=[result]):
            rc = jcode_cli.cmd_ai_quality_gate(_args(path="/tmp"))
        assert rc == 0 and "Total issues: 0" in capsys.readouterr().out

    def test_with_issues_and_verbose(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        issue = SimpleNamespace(line=3, severity="warning", message="bad")
        result = MagicMock(file="a.py", issues=[issue])
        with patch("tools.scripts.rules_engine.check_directory", return_value=[result]):
            rc = jcode_cli.cmd_ai_quality_gate(_args(path=str(tmp_path), verbose=True))
        assert rc == 1
        out = capsys.readouterr().out
        assert "Total issues: 1" in out and "[warning] bad" in out

    def test_issues_without_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = MagicMock(issues=[SimpleNamespace(line=1, severity="e", message="m")])
        result.file = "x.py"
        with patch("tools.scripts.rules_engine.check_directory", return_value=[result]):
            assert jcode_cli.cmd_ai_quality_gate(_args()) == 1
        assert "Line 1" not in capsys.readouterr().out


class TestAiPrReview:
    def test_no_diff(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("tools.scripts.ai_pr_reviewer.get_git_diff", return_value=""),
            patch("tools.scripts.ai_pr_reviewer.review_diff") as rd,
        ):
            rc = jcode_cli.cmd_ai_pr_review(_args())
        assert rc == 0 and "No changes" in capsys.readouterr().out
        rd.assert_not_called()

    def test_findings(self, capsys: pytest.CaptureFixture[str]) -> None:
        finding = {"category": "Security", "rule": "R1", "description": "d"}
        with (
            patch("tools.scripts.ai_pr_reviewer.get_git_diff", return_value="+diff"),
            patch(
                "tools.scripts.ai_pr_reviewer.review_diff",
                return_value={"findings": [finding]},
            ),
        ):
            assert jcode_cli.cmd_ai_pr_review(_args()) == 1
        assert "[Security] R1" in capsys.readouterr().out

    def test_clean_diff(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("tools.scripts.ai_pr_reviewer.get_git_diff", return_value="+diff"),
            patch("tools.scripts.ai_pr_reviewer.review_diff", return_value={"findings": []}),
        ):
            assert jcode_cli.cmd_ai_pr_review(_args()) == 0
        assert "No issues found" in capsys.readouterr().out


class TestCaseQualityAndForwarders:
    def test_single_case(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        metrics = SimpleNamespace(
            case_name="c",
            overall_score=88.0,
            authenticity_score=9.0,
            efficiency_credibility=8.5,
            insight_quality=9.2,
            completeness=8.0,
            cross_references=7.5,
            issues=["i1"],
            strengths=["s1"],
        )
        analyzer = MagicMock()
        analyzer.analyze_case.return_value = metrics
        with patch(
            "tools.scripts.analyze_case_quality.CaseStudyQualityAnalyzer",
            return_value=analyzer,
        ):
            rc = jcode_cli.cmd_case_quality(_args(case=str(tmp_path / "c.md")))
        assert rc == 0 and "Overall: 88.0/100" in capsys.readouterr().out

    def test_all_cases(self, capsys: pytest.CaptureFixture[str]) -> None:
        analyzer = MagicMock()
        analyzer.generate_report.return_value = {"n": 1}
        with (
            patch(
                "tools.scripts.analyze_case_quality.CaseStudyQualityAnalyzer",
                return_value=analyzer,
            ),
            patch("tools.scripts.analyze_case_quality.format_report", return_value="REPORT"),
        ):
            assert jcode_cli.cmd_case_quality(_args(case=None)) == 0
        assert "REPORT" in capsys.readouterr().out

    def test_validate_case_forwards_argv(self) -> None:
        """cmd 内 from-import → patch 源头模块属性; argv 被改写后转发。"""
        seen: dict[str, list[str]] = {}

        def fake_main() -> int:
            import sys

            seen["argv"] = list(sys.argv)
            return 0

        with patch("tools.scripts.validate_case_study.main", fake_main):
            rc = jcode_cli.cmd_validate_case_study(_args(rest=["--anything"]))
        assert rc == 0
        assert seen["argv"][0] == "validate_case_study.py"

    def test_create_case_forwards(self) -> None:
        calls: list[list[str]] = []

        def fake_main() -> None:
            import sys

            calls.append(list(sys.argv))

        with patch("tools.scripts.create_case_study.main", fake_main):
            rc = jcode_cli.cmd_create_case_study(_args(rest=["--title", "t"]))
        assert rc == 0 and calls[0][0] == "create_case_study.py"


class TestDorCheck:
    def test_pass_and_fail(self, capsys: pytest.CaptureFixture[str]) -> None:
        checker = MagicMock()
        checker.evaluate_intent.side_effect = [
            {"passed": True, "score": 6, "violations": []},
            {"passed": False, "score": 3, "violations": ["v1"]},
        ]
        with (
            patch.object(jcode_cli, "get_project_root", return_value=Path(".")),
            patch("tools.scripts.dor_checker.DoRChecker", return_value=checker),
        ):
            assert jcode_cli.cmd_dor_check(_args(intent="build feature")) == 0
            assert jcode_cli.cmd_dor_check(_args(intent="vague")) == 1
        out = capsys.readouterr().out
        assert "Score: 6/7" in out and "- v1" in out


class TestGraphVisualTelemetryAttestation:
    def test_semantic_graph_with_query(self, capsys: pytest.CaptureFixture[str]) -> None:
        graph = MagicMock()
        graph.query_impact.return_value = ["mod_a", "mod_b"]
        with (
            patch.object(jcode_cli, "get_project_root", return_value=Path(".")),
            patch("tools.scripts.semantic_code_graph.SemanticCodeGraph", return_value=graph),
        ):
            rc = jcode_cli.cmd_semantic_graph(_args(query="mod_a"))
        assert rc == 0 and "mod_b" in capsys.readouterr().out

    def test_semantic_graph_without_query(self) -> None:
        graph = MagicMock()
        with (
            patch.object(jcode_cli, "get_project_root", return_value=Path(".")),
            patch("tools.scripts.semantic_code_graph.SemanticCodeGraph", return_value=graph),
        ):
            assert jcode_cli.cmd_semantic_graph(_args(query=None)) == 0

    def test_arch_visualizer_writes_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out_file = tmp_path / "arch.md"
        with (
            patch.object(jcode_cli, "get_project_root", return_value=Path(".")),
            patch(
                "tools.scripts.arch_visualizer.scan_python_imports",
                return_value={"a": ["b"]},
            ),
            patch(
                "tools.scripts.arch_visualizer.generate_mermaid_diagram",
                return_value="graph TD; a->b;",
            ),
        ):
            rc = jcode_cli.cmd_arch_visualizer(_args(output=str(out_file)))
        assert rc == 0
        text = out_file.read_text(encoding="utf-8")
        assert "mermaid" in text and "a->b;" in text

    def test_metrics_telemetry(self, capsys: pytest.CaptureFixture[str]) -> None:
        telemetry = MagicMock()
        telemetry.collect_metrics.return_value = {"commits": 10}
        with (
            patch.object(jcode_cli, "get_project_root", return_value=Path(".")),
            patch("tools.scripts.metrics_telemetry.MetricsTelemetry", return_value=telemetry),
        ):
            assert jcode_cli.cmd_metrics_telemetry(_args()) == 0
        assert "commits" in capsys.readouterr().out

    def test_audit_attestation_with_intent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        ledger = MagicMock()
        ledger.generate_report.return_value = "LEDGER"
        with (
            patch.object(jcode_cli, "get_project_root", return_value=tmp_path),
            patch("tools.scripts.audit_attestation.AuditAttestationLedger", return_value=ledger),
        ):
            assert jcode_cli.cmd_audit_attestation(_args(intent="ship it")) == 0
        ledger.record_trace.assert_called_once()
        assert "LEDGER" in capsys.readouterr().out

    def test_audit_attestation_without_intent(self, tmp_path: Path) -> None:
        ledger = MagicMock()
        ledger.generate_report.return_value = "R"
        with (
            patch.object(jcode_cli, "get_project_root", return_value=tmp_path),
            patch("tools.scripts.audit_attestation.AuditAttestationLedger", return_value=ledger),
        ):
            assert jcode_cli.cmd_audit_attestation(_args(intent=None)) == 0
        ledger.record_trace.assert_not_called()


class TestWorkflowAndMain:
    def test_workflow_success_and_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        wf = MagicMock()
        wf.run_full_pipeline.side_effect = [True, False]
        with patch("tools.scripts.jcode_ai_native_workflow.JCodeAINativeWorkflow", return_value=wf):
            assert jcode_cli.cmd_ai_native_workflow(_args(intent="do x")) == 0
            assert jcode_cli.cmd_ai_native_workflow(_args(intent=None)) == 1
        wf.run_full_pipeline.assert_called_with("Feature Delivery via AI-Native SDLC")

    @pytest.mark.parametrize(
        ("argv", "expected"),
        [
            (["jcode"], 1),  # 无命令 → help + 1
        ],
    )
    def test_main_no_command(self, argv: list[str], expected: int, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", argv):
            assert jcode_cli.main() == expected

    def test_main_dispatches_subcommand(self) -> None:
        with (
            patch("sys.argv", ["jcode", "ai-pr-review"]),
            patch("tools.scripts.ai_pr_reviewer.get_git_diff", return_value=""),
        ):
            assert jcode_cli.main() == 0

    def test_main_catches_exception(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["jcode", "metrics-telemetry"]),
            patch.object(
                jcode_cli,
                "cmd_metrics_telemetry",
                side_effect=RuntimeError("boom"),
            ),
        ):
            assert jcode_cli.main() == 1
        assert "Error: boom" in capsys.readouterr().out

    def test_main_keyboard_interrupt_returns_130(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["jcode", "metrics-telemetry"]),
            patch.object(jcode_cli, "cmd_metrics_telemetry", side_effect=KeyboardInterrupt),
        ):
            assert jcode_cli.main() == 130
        assert "Interrupted" in capsys.readouterr().out
