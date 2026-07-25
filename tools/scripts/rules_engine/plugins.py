"""Plugin system for the rules engine.

Allows extending the engine with custom checkers without modifying core code.

Usage:
    # Register a custom checker
    from rules_engine.plugins import register_checker, CheckerPlugin

    class MyChecker(CheckerPlugin):
        name = "my_checker"
        supported_languages = ["python", "javascript"]

        def check(self, filepath, content, lines, lang, rules):
            issues = []
            # Your checking logic here
            return issues

    register_checker(MyChecker())

    # Or use the decorator
    @register_checker_decorator(name="my_checker", languages=["python"])
    def my_check(filepath, content, lines, lang, rules):
        return []

    # Auto-discover plugins from a directory
    from rules_engine.plugins import discover_plugins
    discover_plugins(Path("my_plugins/"))

    # List registered plugins
    from rules_engine.plugins import list_plugins
    for plugin in list_plugins():
        print(f"{plugin.name}: {plugin.supported_languages}")
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import Issue


class CheckerPlugin(ABC):
    """Base class for checker plugins.

    Subclass this to create a custom checker. Set class attributes
    and implement the check() method.
    """

    name: str = ""
    supported_languages: list[str] = []
    priority: int = 100  # Lower = runs first

    @abstractmethod
    def check(
        self,
        filepath: Path,
        content: str,
        lines: list[str],
        lang: str,
        rules: dict[str, Any],
    ) -> list[Issue]:
        """Run checker and return list of Issues."""
        ...

    def __repr__(self) -> str:
        return f"<Plugin {self.name} langs={self.supported_languages}>"


# ──────────────────────────────────────────────────────────
# Plugin registry
# ──────────────────────────────────────────────────────────

_registry: list[CheckerPlugin] = []


def register_checker(plugin: CheckerPlugin) -> None:
    """Register a checker plugin.

    Raises ValueError if a plugin with the same name is already registered.
    """
    if any(p.name == plugin.name for p in _registry):
        raise ValueError(f"Plugin '{plugin.name}' already registered")
    _registry.append(plugin)
    _registry.sort(key=lambda p: p.priority)


def unregister_checker(name: str) -> bool:
    """Unregister a checker plugin by name. Returns True if found and removed."""
    global _registry
    before = len(_registry)
    _registry = [p for p in _registry if p.name != name]
    return len(_registry) < before


def list_plugins() -> list[CheckerPlugin]:
    """Return list of registered plugins (sorted by priority)."""
    return list(_registry)


def get_plugins_for_language(lang: str) -> list[CheckerPlugin]:
    """Return plugins that support the given language."""
    return [p for p in _registry if lang in p.supported_languages or not p.supported_languages]


def clear_plugins() -> None:
    """Clear all registered plugins. Mainly for testing."""
    _registry.clear()


# ──────────────────────────────────────────────────────────
# Decorator for function-based plugins
# ──────────────────────────────────────────────────────────


class _FunctionPlugin(CheckerPlugin):
    """Wrapper that turns a function into a CheckerPlugin."""

    def __init__(
        self,
        func: Any,
        name: str,
        languages: list[str],
        priority: int = 100,
    ) -> None:
        self._func = func
        self.name = name
        self.supported_languages = languages
        self.priority = priority

    def check(
        self,
        filepath: Path,
        content: str,
        lines: list[str],
        lang: str,
        rules: dict[str, Any],
    ) -> list[Issue]:
        result: list[Issue] = self._func(filepath, content, lines, lang, rules)
        return result


def register_checker_decorator(
    name: str,
    languages: list[str] | None = None,
    priority: int = 100,
) -> Any:
    """Decorator to register a function as a checker plugin.

    Usage:
        @register_checker_decorator(name="my_check", languages=["python"])
        def my_check(filepath, content, lines, lang, rules):
            return []
    """

    def decorator(func: Any) -> Any:
        plugin = _FunctionPlugin(func, name=name, languages=languages or [], priority=priority)
        register_checker(plugin)
        return func

    return decorator


# ──────────────────────────────────────────────────────────
# Plugin discovery
# ──────────────────────────────────────────────────────────


def discover_plugins(directory: Path) -> int:
    """Auto-discover and register plugins from a directory.

    Each .py file in the directory should define a module-level
    `plugin` attribute that is a CheckerPlugin instance, or define
    a `register` function that registers plugins.

    Returns number of plugins discovered.
    """
    if not directory.exists() or not directory.is_dir():
        return 0

    count = 0
    for py_file in sorted(directory.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        try:
            before = len(_registry)
            spec = importlib.util.spec_from_file_location(
                f"rules_engine_plugins.{py_file.stem}",
                py_file,
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Check for module-level plugin attribute
            plugin = getattr(module, "plugin", None)
            if isinstance(plugin, CheckerPlugin):
                register_checker(plugin)

            # Check for register() function
            register_fn = getattr(module, "register", None)
            if callable(register_fn):
                register_fn()

            # Count any plugins registered during module load
            after = len(_registry)
            count += after - before
        except Exception:
            # Skip plugins that fail to load
            continue

    return count
