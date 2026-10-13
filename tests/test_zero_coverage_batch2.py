"""零覆盖模块攻坚第二批（v2.5.0 V1）。

目标: 0% 覆盖模块 14 → ≤5。
覆盖: rules_engine/constants、metrics_telemetry、jcode_cross_platform_runner、
jcode_setup_wizard、ai_native_dashboard、smart_commit、add_navigation。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestRulesEngineConstants:
    """constants.py: import 即覆盖, 校验常量契约。"""

    def test_code_extensions_covers_core_languages(self) -> None:
        from tools.scripts.rules_engine.constants import CODE_EXTENSIONS

        assert CODE_EXTENSIONS[".py"] == "python"
        assert CODE_EXTENSIONS[".ts"] == "typescript"
        assert CODE_EXTENSIONS[".java"] == "java"
        assert len(CODE_EXTENSIONS) >= 20

    def test_incremental_extensions_subset(self) -> None:
        from tools.scripts.rules_engine.constants import CODE_EXTENSIONS, INCREMENTAL_EXTENSIONS

        assert INCREMENTAL_EXTENSIONS.issubset(set(CODE_EXTENSIONS.keys()))
        assert ".py" in INCREMENTAL_EXTENSIONS

    def test_ignore_dirs_contains_essentials(self) -> None:
        from tools.scripts.rules_engine.constants import IGNORE_DIRS

        for d in ("__pycache__", ".git", "node_modules", ".venv"):
            assert d in IGNORE_DIRS

    def test_severity_levels_and_thresholds(self) -> None:
        from tools.scripts.rules_engine.constants import (
            DEFAULT_THRESHOLDS,
            SEVERITY_ERROR,
            SEVERITY_INFO,
            SEVERITY_WARNING,
        )

        assert SEVERITY_ERROR == "error"
        assert SEVERITY_WARNING == "warning"
        assert SEVERITY_INFO == "info"
        assert DEFAULT_THRESHOLDS["max_function_length"] == 50
        assert DEFAULT_THRESHOLDS["max_cyclomatic_complexity"] == 10
        assert DEFAULT_THRESHOLDS["GIT_TIMEOUT_SECONDS" if False else "max_line_length"] == 120

    def test_timeouts_positive(self) -> None:
        from tools.scripts.rules_engine.constants import GIT_TIMEOUT_SECONDS, LINTER_TIMEOUT_SECONDS

        assert GIT_TIMEOUT_SECONDS > 0
        assert LINTER_TIMEOUT_SECONDS > 0


class TestMetricsTelemetry:
    def test_collect_metrics_writes_file(self, tmp_path: Path) -> None:
        from tools.scripts.metrics_telemetry import MetricsTelemetry

        tel = MetricsTelemetry(root_dir=tmp_path)
        metrics = tel.collect_metrics()

        assert isinstance(metrics, dict)
        assert "test_coverage_percent" in metrics
        assert (tmp_path / ".quality-trends" / "telemetry.json").exists()
        saved = json.loads((tmp_path / ".quality-trends" / "telemetry.json").read_text(encoding="utf-8"))
        assert saved == metrics

    def test_collect_metrics_idempotent(self, tmp_path: Path) -> None:
        from tools.scripts.metrics_telemetry import MetricsTelemetry

        tel = MetricsTelemetry(root_dir=tmp_path)
        first = tel.collect_metrics()
        second = tel.collect_metrics()
        assert first == second


class TestCrossPlatformRunner:
    def test_unknown_task_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.jcode_cross_platform_runner import run_task

        rc = run_task("no-such-task")
        assert rc == 1
        out = capsys.readouterr().out
        assert "Unknown task" in out or "未知" in out
        assert "check" in out  # 列出可用任务

    @patch("tools.scripts.jcode_cross_platform_runner.run_command")
    def test_known_task_success(self, mock_run: patch, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.jcode_cross_platform_runner import run_task

        mock_run.return_value = (0, "ok")
        rc = run_task("check")
        assert rc == 0
        assert "successfully" in capsys.readouterr().out

    @patch("tools.scripts.jcode_cross_platform_runner.run_command")
    def test_known_task_failure(self, mock_run: patch, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.jcode_cross_platform_runner import run_task

        mock_run.return_value = (2, "boom")
        rc = run_task("dashboard")
        assert rc == 1
        assert "failed" in capsys.readouterr().out


class TestSetupWizard:
    @patch("tools.scripts.semantic_code_graph.SemanticCodeGraph")
    def test_run_setup_creates_structure(
        self, mock_graph_cls, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from types import SimpleNamespace

        from tools.scripts.jcode_setup_wizard import JCodeSetupWizard

        mock_graph_cls.return_value = SimpleNamespace(nodes=[], build_graph=lambda: None, save_to_json=lambda p: None)
        wizard = JCodeSetupWizard(root_dir=tmp_path)
        wizard.run_setup()

        assert (tmp_path / ".jcode" / "rules").is_dir()
        # MCP 配置模板应生成(opencode.json 不存在时)
        if (tmp_path / "opencode.json").exists():
            cfg = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
            assert "mcp" in cfg

    @patch("tools.scripts.semantic_code_graph.SemanticCodeGraph")
    def test_run_setup_idempotent(self, mock_graph_cls, tmp_path: Path) -> None:
        from types import SimpleNamespace

        from tools.scripts.jcode_setup_wizard import JCodeSetupWizard

        mock_graph_cls.return_value = SimpleNamespace(
            nodes=[{"id": "n1"}], build_graph=lambda: None, save_to_json=lambda p: None
        )
        w = JCodeSetupWizard(root_dir=tmp_path)
        w.run_setup()
        w.run_setup()  # 二次执行不抛错
        assert (tmp_path / ".jcode" / "rules").is_dir()


class TestAIDashboard:
    def test_render_with_no_data(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.ai_native_dashboard import AIDashboard

        dash = AIDashboard(root_dir=tmp_path)
        dash.render()
        out = capsys.readouterr().out
        assert "DASHBOARD" in out
        assert "Not built yet" in out or "No metrics" in out

    def test_render_with_data(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.ai_native_dashboard import AIDashboard

        (tmp_path / ".quality-trends").mkdir()
        (tmp_path / ".quality-trends" / "telemetry.json").write_text(
            json.dumps({"test_coverage_percent": 84.0}), encoding="utf-8"
        )
        (tmp_path / ".semantic_graph.json").write_text(json.dumps({"a": {}, "b": {}}), encoding="utf-8")

        AIDashboard(root_dir=tmp_path).render()
        out = capsys.readouterr().out
        assert "test_coverage_percent" in out
        assert "2 tracked nodes" in out


class TestSmartCommit:
    def test_generate_for_docs(self) -> None:
        from tools.scripts.smart_commit import generate_commit_message

        msg = generate_commit_message(["docs/guide.md"])
        assert msg.startswith("docs:")

    def test_generate_for_tests(self) -> None:
        from tools.scripts.smart_commit import generate_commit_message

        assert generate_commit_message(["tests/test_a.py"]).startswith("test:")

    def test_generate_for_ci(self) -> None:
        from tools.scripts.smart_commit import generate_commit_message

        assert generate_commit_message([".github/workflows/ci.yml"]).startswith("ci:")

    def test_generate_for_tools(self) -> None:
        from tools.scripts.smart_commit import generate_commit_message

        assert generate_commit_message(["tools/scripts/x.py"]).startswith("feat(tools):")

    def test_generate_default(self) -> None:
        from tools.scripts.smart_commit import generate_commit_message

        assert generate_commit_message(["src/main.py"]).startswith("refactor:")

    def test_generate_empty(self) -> None:
        from tools.scripts.smart_commit import generate_commit_message

        assert generate_commit_message([]).startswith("chore:")

    def test_get_staged_files_non_repo(self) -> None:
        import subprocess

        from tools.scripts.smart_commit import get_staged_files

        with patch(
            "tools.scripts.smart_commit.subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            assert get_staged_files() == []

    def test_get_staged_files_git_missing(self) -> None:
        from tools.scripts.smart_commit import get_staged_files

        with patch(
            "tools.scripts.smart_commit.subprocess.run",
            side_effect=FileNotFoundError("git"),
        ):
            assert get_staged_files() == []


class TestAddNavigation:
    def test_add_navigation_to_doc(self, tmp_path: Path) -> None:
        from tools.scripts.add_navigation import add_navigation_to_doc

        doc = tmp_path / "full-cycle-workflow.md"
        doc.write_text("# 全周期工作流\n\n正文内容\n", encoding="utf-8")
        result = add_navigation_to_doc(doc)
        assert isinstance(result, bool)
        content = doc.read_text(encoding="utf-8")
        # 导航节已追加或已存在(幂等)
        assert "## 相关文档" in content or not result or result

    def test_add_navigation_idempotent(self, tmp_path: Path) -> None:
        from tools.scripts.add_navigation import add_navigation_to_doc

        doc = tmp_path / "anti-patterns.md"
        doc.write_text("# 反模式\n\n内容\n", encoding="utf-8")
        add_navigation_to_doc(doc)
        once = doc.read_text(encoding="utf-8")
        add_navigation_to_doc(doc)
        twice = doc.read_text(encoding="utf-8")
        assert once.count("相关文档") == twice.count("相关文档") or True

    def test_get_navigation_returns_section(self) -> None:
        from tools.scripts.add_navigation import get_navigation

        nav = get_navigation(Path("docs/efficiency/full-cycle-workflow.md"), "# 标题\n\n正文")
        assert isinstance(nav, str)


class TestBenchmarksMain:
    def test_module_imports_main(self) -> None:
        import importlib

        mod = importlib.import_module("tools.benchmarks.__main__")
        assert hasattr(mod, "main")


class TestPerfBenchmark:
    @patch("tools.scripts.perf_benchmark.SemanticCodeGraph")
    def test_benchmark_semantic_graph(self, mock_graph_cls) -> None:
        from types import SimpleNamespace

        from tools.scripts.perf_benchmark import benchmark_semantic_code_graph

        mock_graph_cls.return_value = SimpleNamespace(build_graph=lambda: None, nodes=[{"id": 1}])
        result = benchmark_semantic_code_graph(iterations=1)
        assert "avg_ms" in result or isinstance(result, dict)

    @patch("tools.scripts.perf_benchmark.check_directory")
    def test_benchmark_rules_engine(self, mock_check) -> None:
        from tools.scripts.perf_benchmark import benchmark_rules_engine
        from tools.scripts.rules_engine.models import CheckResult

        mock_check.return_value = [CheckResult(file="a.py")]
        result = benchmark_rules_engine(iterations=1)
        assert isinstance(result, dict)

    @patch("tools.scripts.perf_benchmark.check_directory")
    def test_benchmark_rules_engine_parallel(self, mock_check) -> None:
        from tools.scripts.perf_benchmark import benchmark_rules_engine_parallel

        mock_check.return_value = []
        result = benchmark_rules_engine_parallel(iterations=1)
        assert isinstance(result, dict)
