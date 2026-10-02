"""Rules Engine - Pluggable code quality checking engine.

This package provides a modular rules engine for code quality checks,
supporting multiple languages and pluggable checkers.

Usage:
    # Check a single file
    from rules_engine import check_file
    result = check_file(Path("my_script.py"))
    logger.info(f"Passed: {result.passed}, Issues: {len(result.issues)}")

    # Check a directory
    from rules_engine import check_directory
    results = check_directory(Path("src/"))
    for r in results:
        if not r.passed:
            logger.info(f"{r.file}: {r.error_count} errors")

    # Load language-specific rules
    from rules_engine import load_rules_for_language
    rules = load_rules_for_language("python")

    # Use individual checkers
    from rules_engine.anti_pattern_checker import check_anti_patterns
    from rules_engine.complexity_checker import check_python_complexity
    from rules_engine.naming_checker import check_naming_conventions

Architecture:
    - models.py: Core data models (Issue, CheckResult, Severity, HealthScore)
    - rule_loader.py: YAML rule loading, caching, and merging
    - anti_pattern_checker.py: Regex-based anti-pattern detection
    - naming_checker.py: Naming convention validation
    - complexity_checker.py: AST-based complexity metrics (Python) + regex (JS/TS)
    - checker.py: Main orchestrator with external linter integration
"""

from .auto_fix import apply_fixes, apply_fixes_to_directory, format_fix_results
from .checker import check_directory, check_file
from .models import CheckResult, Issue, Severity
from .plugins import (
    CheckerPlugin,
    clear_plugins,
    discover_plugins,
    get_plugins_for_language,
    list_plugins,
    register_checker,
    register_checker_decorator,
    unregister_checker,
)
from .rule_loader import load_rules_for_language

__all__ = [
    "CheckResult",
    "CheckerPlugin",
    "Issue",
    "Severity",
    "apply_fixes",
    "apply_fixes_to_directory",
    "check_directory",
    "check_file",
    "clear_plugins",
    "discover_plugins",
    "format_fix_results",
    "get_plugins_for_language",
    "list_plugins",
    "load_rules_for_language",
    "register_checker",
    "register_checker_decorator",
    "unregister_checker",
]

__version__ = "1.2.0"
