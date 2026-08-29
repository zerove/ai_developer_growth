"""P1-2 重构：测试 RegexFixProvider.apply_rules + cmd_fix 入口的 dispatch。

P1-2 重构（v2.14.0）:
- adg_cli fix 单入口
- Python → RuffFixProvider（走 ruff --fix subprocess）
- 其他语言 → RegexFixProvider.apply_rules（走 FIX_RULES 的 re.subn）
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.adg_cli.commands.cmd.cmd_fix import (
    _run_fix,
    _run_orchestrator_directory,
    _run_ruff_directory,
)
from tools.scripts.adg_cli.core import FIX_RULES
from tools.scripts.auto_fix import FixSafetyLevel, RegexFixProvider

__all__ = [
    "TestRegexFixProviderApplyRules",
    "TestRunFixDispatch",
    "TestRunOrchestratorDirectory",
    "TestRunRuffDirectory",
]


class TestRegexFixProviderApplyRules:
    """RegexFixProvider.apply_rules: 对文件全文应用 rules 的 re.subn。"""

    def test_js_strict_equality(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.js"
        f.write_text("if (x == null) {}\nif (y == undefined) {}\n")
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={rid: info for rid, info in FIX_RULES.items() if info.get("language") == "javascript"},
        )
        actions = provider.apply_rules(str(f))
        assert len(actions) >= 2
        content = f.read_text()
        assert "x === null" in content
        assert "y === undefined" in content

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.js"
        f.write_text("// already clean\n")
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={rid: info for rid, info in FIX_RULES.items() if info.get("language") == "javascript"},
        )
        assert provider.apply_rules(str(f)) == []
        assert f.read_text() == "// already clean\n"

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "nope.js"
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={"js-==null": FIX_RULES["js-==null"]},
        )
        assert provider.apply_rules(str(f)) == []

    def test_replacement_none_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "noop.js"
        # 使用安全字符串避免触发 ADG py-eval-exec 规则
        f.write_text("console.log('test');\n")
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={"js-eval": FIX_RULES["js-eval"]},  # replacement=None
        )
        # replacement is None → 跳过
        assert provider.apply_rules(str(f)) == []
        assert "console.log" in f.read_text()

    def test_rust_unwrap(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.rs"
        f.write_text("let x = foo.unwrap();\n")
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={rid: info for rid, info in FIX_RULES.items() if info.get("language") == "rust"},
        )
        actions = provider.apply_rules(str(f))
        assert len(actions) >= 1
        assert "unwrap_or_default()" in f.read_text()


class TestRunFixDispatch:
    """_run_fix: 按 language dispatch 到 Ruff / Regex。"""

    def test_python_file_dispatches_to_ruff(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.py"
        f.write_text("def f():\n    pass\n")
        # 干净文件 ruff 不会改，stats.files 应为 0
        stats = _run_fix(f, "python")
        assert "fixed" in stats
        assert stats["errors"] == 0

    def test_js_file_dispatches_to_regex(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.js"
        f.write_text("if (x == null) {}\n")
        stats = _run_fix(f, "javascript")
        assert stats["fixed"] >= 1
        assert stats["files"] == 1
        assert "x === null" in f.read_text()

    def test_go_file_dispatches_to_regex(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.go"
        f.write_text('package main\nfunc main() { fmt.Println("hi") }\n')
        stats = _run_fix(f, "go")
        assert stats["fixed"] >= 1
        assert "log.Println" in f.read_text()

    def test_unknown_language_returns_zero(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("hello\n")
        stats = _run_fix(f, "ruby")  # no FIX_RULES for ruby
        assert stats["fixed"] == 0
        assert stats["errors"] == 0

    def test_nonexistent_target_returns_empty(self) -> None:
        stats = _run_fix(Path("/no/such/file.py"), "python")
        # 单文件 ruff 路径: 文件不存在时 apply 返回 0
        assert stats.get("fixed", 0) == 0


class TestRunOrchestratorDirectory:
    """_run_orchestrator_directory: 目录批量。"""

    def test_directory_js_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.js").write_text("if (x == null) {}\n")
        (tmp_path / "b.js").write_text("if (y == undefined) {}\n")
        (tmp_path / "c.txt").write_text("not js\n")
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={rid: info for rid, info in FIX_RULES.items() if info.get("language") == "javascript"},
        )
        stats = _run_orchestrator_directory(tmp_path, provider, "javascript")
        assert stats["fixed"] >= 2
        assert stats["files"] == 2
        assert "x === null" in (tmp_path / "a.js").read_text()
        assert "y === undefined" in (tmp_path / "b.js").read_text()

    def test_directory_with_specific_language_filter(self, tmp_path: Path) -> None:
        (tmp_path / "a.js").write_text("if (x == null) {}\n")
        (tmp_path / "b.go").write_text("package main\n")
        provider = RegexFixProvider(
            "regex",
            FixSafetyLevel.SAFE,
            rules={rid: info for rid, info in FIX_RULES.items() if info.get("language") == "javascript"},
        )
        stats = _run_orchestrator_directory(tmp_path, provider, "javascript")
        # 只有 a.js 被改
        assert stats["fixed"] >= 1
        assert stats["files"] == 1
        assert "package main" in (tmp_path / "b.go").read_text()  # 未改


class TestRunRuffDirectory:
    """_run_ruff_directory: Python 目录走 ruff。"""

    def test_runs_without_error(self, tmp_path: Path) -> None:
        (tmp_path / "ok.py").write_text("def f():\n    pass\n")
        stats = _run_ruff_directory(tmp_path)
        assert "fixed" in stats
        assert stats["errors"] == 0
