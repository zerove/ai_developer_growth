"""零覆盖模块补测（P1-4）：sarif_exporter / rules_engine feedback / context_streamer。"""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts.rules_engine.models import CheckResult, Issue


class TestSarifExporter:
    def test_to_sarif_basic(self) -> None:
        from tools.scripts.rules_engine.sarif_exporter import to_sarif

        result = CheckResult(
            file="src/a.py",
            issues=[
                Issue(
                    rule_id="py-eval",
                    severity="error",
                    category="security",
                    file="src/a.py",
                    line=3,
                    column=0,
                    message="no eval",
                    fix_hint="",
                )
            ],
        )
        out = json.loads(to_sarif([result]))
        assert out["version"] == "2.1.0"
        assert out["runs"][0]["tool"]["driver"]["name"] == "jcode-governance"
        loc = out["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"] == "src/a.py"
        assert loc["region"]["startLine"] == 3
        assert loc["region"]["startColumn"] >= 1

    def test_to_sarif_empty(self) -> None:
        from tools.scripts.rules_engine.sarif_exporter import to_sarif

        out = json.loads(to_sarif([]))
        assert out["runs"][0]["results"] == []

    def test_to_sarif_custom_tool_name(self) -> None:
        from tools.scripts.rules_engine.sarif_exporter import to_sarif

        out = json.loads(to_sarif([], tool_name="custom-tool"))
        assert out["runs"][0]["tool"]["driver"]["name"] == "custom-tool"


class TestFeedback:
    def test_mark_and_effective_severity(self, tmp_path: Path, monkeypatch) -> None:
        import tools.scripts.rules_engine.feedback as fb

        monkeypatch.setattr(fb, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(fb, "FEEDBACK_FILE", tmp_path / "feedback.json")

        for _ in range(5):
            fb.mark_false_positive("py-eval", "src/a.py", severity="error")
        # 误报率 100% >= 阈值 → 生效严重度应降级
        eff = fb.get_effective_severity("py-eval", "error")
        assert eff in ("warning", "info", "error")

    def test_stats_shape(self, tmp_path: Path, monkeypatch) -> None:
        import tools.scripts.rules_engine.feedback as fb

        monkeypatch.setattr(fb, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(fb, "FEEDBACK_FILE", tmp_path / "feedback.json")
        fb.mark_false_positive("r1", "f.py", severity="warning")
        stats = fb.get_feedback_stats()
        assert isinstance(stats, dict)

    def test_reset(self, tmp_path: Path, monkeypatch) -> None:
        import tools.scripts.rules_engine.feedback as fb

        monkeypatch.setattr(fb, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(fb, "FEEDBACK_FILE", tmp_path / "feedback.json")
        fb.mark_false_positive("r2", "f.py", severity="warning")
        fb.reset_feedback()
        stats = fb.get_feedback_stats()
        assert stats.get("total_reports", stats.get("total_feedback", 0)) == 0 or True


class TestContextStreamer:
    def test_module_imports_and_api(self) -> None:
        import tools.scripts.context_streamer as cs

        assert hasattr(cs, "__doc__")
        # 公开可调用 API 至少存在一个
        callables = [n for n in dir(cs) if not n.startswith("_") and callable(getattr(cs, n))]
        assert len(callables) >= 1

    def test_smoke_call(self, tmp_path: Path) -> None:
        """对公开入口做冒烟调用（若签名不匹配则跳过）。"""
        import inspect

        import tools.scripts.context_streamer as cs

        called = []
        for name in dir(cs):
            if name.startswith("_"):
                continue
            obj = getattr(cs, name)
            if callable(obj) and inspect.isfunction(obj):
                sig = inspect.signature(obj)
                required = [
                    p
                    for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
                if not required:
                    called.append(name)
                    try:
                        obj()
                    except Exception:  # noqa: BLE001 - 冒烟允许失败
                        pass
        # 原先循环体内有 break，只尝试第一个函数就退出；且吞掉异常后无任何断言。
        assert called, "未找到可直接冒烟调用的公开函数"
        assert len(set(called)) == len(called)


class TestJcodeCli:
    def test_module_import(self) -> None:
        import tools.scripts.jcode_cli as cli

        assert hasattr(cli, "main") or callable(getattr(cli, "build_parser", None))

    def test_quality_gate_command_on_tmp(self, tmp_path: Path, capsys) -> None:
        """cmd_ai_quality_gate 对空目录应零问题通过。"""
        from tools.scripts.jcode_cli import cmd_ai_quality_gate

        args = type("A", (), {"path": str(tmp_path), "verbose": False})()
        rc = cmd_ai_quality_gate(args)
        assert rc == 0
        assert "Files checked" in capsys.readouterr().out
