"""Tests for rules_engine/plugins.py - plugin system."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from rules_engine.models import Issue
from rules_engine.plugins import (
    CheckerPlugin,
    _FunctionPlugin,
    clear_plugins,
    discover_plugins,
    get_plugins_for_language,
    list_plugins,
    register_checker,
    register_checker_decorator,
    unregister_checker,
)

# ──────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────


class _DummyChecker(CheckerPlugin):
    """Test checker implementation."""

    name = "dummy"
    supported_languages = ["python"]
    priority = 50

    def check(self, filepath: Path, content: str, lines: list[str], lang: str, rules: dict[str, Any]) -> list[Issue]:
        return [
            Issue(
                rule_id="dummy-rule",
                severity="warning",
                category="test",
                file=str(filepath),
                line=1,
                message="Dummy check",
            )
        ]


class _AnotherChecker(CheckerPlugin):
    name = "another"
    supported_languages = ["javascript", "typescript"]
    priority = 10

    def check(self, filepath: Path, content: str, lines: list[str], lang: str, rules: dict[str, Any]) -> list[Issue]:
        return []


class _AllLangChecker(CheckerPlugin):
    """Checker that supports all languages (empty list = all)."""

    name = "all_langs"
    supported_languages = []
    priority = 200

    def check(self, filepath: Path, content: str, lines: list[str], lang: str, rules: dict[str, Any]) -> list[Issue]:
        return []


# ──────────────────────────────────────────────────────────
# Tests for CheckerPlugin ABC
# ──────────────────────────────────────────────────────────


class TestCheckerPlugin:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            CheckerPlugin()  # type: ignore[abstract]

    def test_subclass_attributes(self) -> None:
        p = _DummyChecker()
        assert p.name == "dummy"
        assert p.supported_languages == ["python"]
        assert p.priority == 50

    def test_repr(self) -> None:
        p = _DummyChecker()
        assert "dummy" in repr(p)
        assert "python" in repr(p)

    def test_check_returns_issues(self, tmp_path: Path) -> None:
        p = _DummyChecker()
        issues = p.check(tmp_path / "test.py", "x = 1", ["x = 1"], "python", {})
        assert len(issues) == 1
        assert issues[0].rule_id == "dummy-rule"


# ──────────────────────────────────────────────────────────
# Tests for registry functions
# ──────────────────────────────────────────────────────────


class TestRegistry:
    def setup_method(self) -> None:
        clear_plugins()

    def test_register_and_list(self) -> None:
        p = _DummyChecker()
        register_checker(p)
        plugins = list_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "dummy"

    def test_register_duplicate_raises(self) -> None:
        register_checker(_DummyChecker())
        with pytest.raises(ValueError, match="already registered"):
            register_checker(_DummyChecker())

    def test_unregister(self) -> None:
        register_checker(_DummyChecker())
        assert unregister_checker("dummy") is True
        assert list_plugins() == []

    def test_unregister_nonexistent(self) -> None:
        assert unregister_checker("nonexistent") is False

    def test_priority_ordering(self) -> None:
        register_checker(_DummyChecker())  # priority 50
        register_checker(_AnotherChecker())  # priority 10
        plugins = list_plugins()
        assert plugins[0].name == "another"  # lower priority first
        assert plugins[1].name == "dummy"

    def test_clear_plugins(self) -> None:
        register_checker(_DummyChecker())
        register_checker(_AnotherChecker())
        clear_plugins()
        assert list_plugins() == []


# ──────────────────────────────────────────────────────────
# Tests for get_plugins_for_language
# ──────────────────────────────────────────────────────────


class TestGetPluginsForLanguage:
    def setup_method(self) -> None:
        clear_plugins()

    def test_specific_language_match(self) -> None:
        register_checker(_DummyChecker())
        register_checker(_AnotherChecker())
        py_plugins = get_plugins_for_language("python")
        assert len(py_plugins) == 1
        assert py_plugins[0].name == "dummy"

    def test_specific_language_no_match(self) -> None:
        register_checker(_DummyChecker())
        go_plugins = get_plugins_for_language("go")
        assert len(go_plugins) == 0

    def test_empty_languages_matches_all(self) -> None:
        register_checker(_AllLangChecker())
        assert len(get_plugins_for_language("python")) == 1
        assert len(get_plugins_for_language("rust")) == 1
        assert len(get_plugins_for_language("go")) == 1


# ──────────────────────────────────────────────────────────
# Tests for _FunctionPlugin
# ──────────────────────────────────────────────────────────


class TestFunctionPlugin:
    def test_check_delegates_to_function(self, tmp_path: Path) -> None:
        def my_check(filepath: Path, content: str, lines: list[str], lang: str, rules: dict) -> list[Issue]:
            return [
                Issue(
                    rule_id="fn-rule", severity="info", category="test", file=str(filepath), line=1, message="from fn"
                )
            ]

        plugin = _FunctionPlugin(my_check, name="fn_plugin", languages=["python"], priority=5)
        assert plugin.name == "fn_plugin"
        assert plugin.supported_languages == ["python"]
        assert plugin.priority == 5

        issues = plugin.check(tmp_path / "a.py", "", [], "python", {})
        assert len(issues) == 1
        assert issues[0].rule_id == "fn-rule"


# ──────────────────────────────────────────────────────────
# Tests for register_checker_decorator
# ──────────────────────────────────────────────────────────


class TestDecorator:
    def setup_method(self) -> None:
        clear_plugins()

    def test_decorator_registers_plugin(self) -> None:
        @register_checker_decorator(name="dec_check", languages=["python"], priority=42)
        def my_check(filepath: Path, content: str, lines: list[str], lang: str, rules: dict) -> list[Issue]:
            return []

        plugins = list_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "dec_check"
        assert plugins[0].priority == 42
        # Original function is still callable
        result = my_check(Path("x.py"), "", [], "python", {})
        assert result == []

    def test_decorator_no_languages(self) -> None:
        @register_checker_decorator(name="no_lang")
        def check_fn(*args: Any, **kwargs: Any) -> list[Issue]:
            return []

        plugins = list_plugins()
        assert plugins[0].supported_languages == []


# ──────────────────────────────────────────────────────────
# Tests for discover_plugins
# ──────────────────────────────────────────────────────────


class TestDiscoverPlugins:
    def setup_method(self) -> None:
        clear_plugins()

    def test_discover_from_directory(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my_plugins"
        plugin_dir.mkdir()
        plugin_file = plugin_dir / "test_plugin.py"
        plugin_file.write_text(
            "from pathlib import Path\n"
            "from rules_engine.plugins import CheckerPlugin, register_checker\n"
            "from rules_engine.models import Issue\n"
            "from typing import Any\n\n"
            "class DiscoveredChecker(CheckerPlugin):\n"
            "    name = 'discovered'\n"
            "    supported_languages = ['python']\n"
            "    def check(self, filepath, content, lines, lang, rules):\n"
            "        return []\n\n"
            "register_checker(DiscoveredChecker())\n"
        )

        # We need to make rules_engine importable from the plugin file
        # by adding the tools/scripts path
        old_path = sys.path[:]
        sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))
        try:
            count = discover_plugins(plugin_dir)
            assert count >= 1
            plugins = list_plugins()
            assert any(p.name == "discovered" for p in plugins)
        finally:
            sys.path[:] = old_path

    def test_discover_nonexistent_dir(self, tmp_path: Path) -> None:
        assert discover_plugins(tmp_path / "nonexistent") == 0

    def test_discover_skips_underscore_files(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        (plugin_dir / "_internal.py").write_text("# skipped")
        assert discover_plugins(plugin_dir) == 0

    def test_discover_skips_broken_plugins(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        (plugin_dir / "broken.py").write_text("raise ValueError('broken')")
        # Should not raise, just skip
        assert discover_plugins(plugin_dir) == 0

    def test_discover_module_level_plugin(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        plugin_file = plugin_dir / "mod_plugin.py"
        old_path = sys.path[:]
        sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))
        try:
            plugin_file.write_text(
                "from pathlib import Path\n"
                "from rules_engine.plugins import CheckerPlugin\n"
                "from rules_engine.models import Issue\n"
                "from typing import Any\n\n"
                "class ModChecker(CheckerPlugin):\n"
                "    name = 'mod_plugin'\n"
                "    supported_languages = []\n"
                "    def check(self, filepath, content, lines, lang, rules):\n"
                "        return []\n\n"
                "plugin = ModChecker()\n"
            )
            count = discover_plugins(plugin_dir)
            assert count == 1
            assert any(p.name == "mod_plugin" for p in list_plugins())
        finally:
            sys.path[:] = old_path
