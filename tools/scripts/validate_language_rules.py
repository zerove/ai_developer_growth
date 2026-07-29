#!/usr/bin/env python3
"""
Language-Specific Code Quality Validator

Loads machine-readable rules from YAML configs and validates code against:
- Anti-pattern detection (regex-based)
- Naming convention checks
- Quantitative thresholds (function length, nesting depth, etc.)
- Python AST-based analysis (complexity, type annotations)

Modular architecture:
    - validators/models.py     : Data models (Issue, ValidationResult, FixResult)
    - validators/pipeline.py   : Core validation logic
    - validators/cli.py        : CLI entry point
    - validators/health.py     : Health score calculation

Usage:
    python validate_language_rules.py <file_or_dir> --lang python
    python validate_language_rules.py <file_or_dir> --auto-detect
    python validate_language_rules.py <file> --lang typescript --json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────
# Backward-compatible re-exports from validators package
# ──────────────────────────────────────────────────────────
from tools.scripts.validators.health import HealthScore, calculate_health_score  # noqa: F401
from tools.scripts.validators.models import FixResult, Issue, ValidationResult  # noqa: F401
from tools.scripts.validators.pipeline import (  # noqa: F401
    EXTENSION_MAP,
    check_anti_patterns,
    detect_language_from_file,
    load_custom_rules,
    load_rules,
    validate_directory,
    validate_file,
)

__all__ = [
    # Re-exports
    "HealthScore",
    "calculate_health_score",
    "FixResult",
    "Issue",
    "ValidationResult",
    "EXTENSION_MAP",
    "check_anti_patterns",
    "detect_language_from_file",
    "load_custom_rules",
    "load_rules",
    "validate_directory",
    "validate_file",
    # Local functions
    "check_naming_conventions",
    "check_thresholds",
    "check_python_ast",
    "apply_fixes",
    "generate_junit_xml",
    "generate_html_report",
    "generate_sarif",
    "write_report",
    "run_linter_aggregation",
    "print_results",
]

# Rule cache (kept here for backward compatibility with direct imports)
_RULE_CACHE: dict[str, dict[str, Any]] = {}
_FILE_HASH_CACHE: dict[str, str] = {}


# ──────────────────────────────────────────────────────────
# Delegation stubs for functions moved to other modules
# ──────────────────────────────────────────────────────────


def check_naming_conventions(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check naming conventions based on language rules."""
    from .naming_analyzer import check_naming_conventions as _check

    return _check(lines, rules, filepath)


def check_thresholds(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check quantitative thresholds."""
    from .complexity_analyzer import check_thresholds as _check

    return _check(lines, rules, filepath)


def check_python_ast(filepath: str, lines: list[str]) -> list[Issue]:
    """Python-specific AST-based checks."""
    from .complexity_analyzer import check_python_ast as _check

    return _check(filepath, lines)


def apply_fixes(filepath: Path, issues: list[Issue], dry_run: bool = False) -> list[FixResult]:
    """Apply auto-fixes to a file based on issues with fix_replacement."""
    from .fix_applier import apply_fixes as _apply_fixes

    return _apply_fixes(filepath, issues, dry_run)


def generate_junit_xml(results: list[ValidationResult]) -> str:
    """Generate JUnit XML report."""
    from .report_generator import generate_junit_xml as _gen

    return _gen(results)


def generate_html_report(results: list[ValidationResult]) -> str:
    """Generate HTML report."""
    from .report_generator import generate_html_report as _gen

    return _gen(results)


def generate_sarif(results: list[ValidationResult]) -> str:
    """Generate SARIF 2.1.0 report."""
    from .report_generator import generate_sarif as _gen

    return _gen(results)


def write_report(results: list[ValidationResult], format: str, output: Path | None = None) -> str | None:
    """Write report in specified format."""
    from .report_generator import write_report as _write

    return _write(results, format, output)


def run_linter_aggregation(
    dirpath: Path,
    linters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run external linters and aggregate results."""
    from .linter_runner import run_linter_aggregation as _run

    return _run(dirpath, linters)


def print_results(results: list[ValidationResult], use_json: bool = False) -> int:
    """Print validation results. Returns exit code (0=pass)."""
    from .validators.cli import print_results as _print

    return _print(results, use_json)


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules."""
    from .validators.pipeline import _merge_rules as _merge

    return _merge(base, custom)


# ──────────────────────────────────────────────────────────
# Private function re-exports (for backward compatibility with tests)
# ──────────────────────────────────────────────────────────


def _file_hash(filepath: Path) -> str:
    """Quick content hash for incremental checks."""
    try:
        content = filepath.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except OSError:
        return ""


def _load_cache(cache_file: Path) -> dict[str, str]:
    """Load file hash cache from disk."""
    if cache_file.exists():
        try:
            result: dict[str, str] = json.loads(cache_file.read_text())
            return result
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache_file: Path, cache: dict[str, str]) -> None:
    """Save file hash cache to disk."""
    try:
        cache_file.write_text(json.dumps(cache))
    except OSError:
        pass


def _get_supported_files(dirpath: Path, exclude: list[str]) -> list[Path]:
    """Get all supported files in a directory."""
    exclude = exclude or ["node_modules", "target", "vendor", ".git", "__pycache__", ".venv"]
    files = []
    for fp in sorted(dirpath.rglob("*")):
        if not fp.is_file():
            continue
        if any(ex in fp.parts for ex in exclude):
            continue
        if detect_language_from_file(fp):
            files.append(fp)
    return files


def _calc_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity for an AST node."""
    from .complexity_analyzer import calc_cyclomatic_complexity

    return calc_cyclomatic_complexity(node)


def _extract_function_lines(lines: list[str], language: str) -> list[tuple[str, int, int]]:
    """Extract function name, start line, end line."""
    from .complexity_analyzer import extract_function_lines

    return extract_function_lines(lines, language)


def _max_nesting_depth(lines: list[str], language: str = "") -> int:
    """Calculate maximum nesting depth from lines."""
    from .complexity_analyzer import max_nesting_depth

    return max_nesting_depth(lines, language)


def _max_python_indent_depth(lines: list[str]) -> int:
    """Calculate max nesting depth for Python using indentation."""
    from .complexity_analyzer import _max_python_indent_depth

    return _max_python_indent_depth(lines)


# ──────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────


def main() -> int:
    """Main entry point."""
    from .validators.cli import main as _main

    return _main()


if __name__ == "__main__":
    from _common import handle_error  # type: ignore[import-not-found]

    try:
        sys.exit(main())
    except Exception as e:
        handle_error(e, script="validate_language_rules")
