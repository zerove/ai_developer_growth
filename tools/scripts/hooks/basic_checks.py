"""基础检查函数: lint, format, typecheck, test, security."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    CheckResult = tuple[bool, str]

# Supported code file extensions for file-based checks
CODE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".cs",
        ".php",
        ".rb",
        ".cpp",
        ".swift",
        ".scala",
        ".ex",
        ".exs",
        ".lua",
        ".zig",
        ".r",
        ".R",
        ".clj",
        ".hs",
        ".dart",
        ".ps1",
    }
)

# Subset used for incremental/diff checks (languages with active rule support)
INCREMENTAL_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".cs",
        ".php",
        ".rb",
        ".cpp",
        ".swift",
        ".scala",
        ".dart",
    }
)


def _run_subprocess(
    cmd: list[str],
    *,
    timeout: int = 120,
    description: str = "",
) -> tuple[bool, str]:
    """Run a subprocess command and return (passed, output).

    Args:
        cmd: Command and arguments to execute.
        timeout: Timeout in seconds.
        description: Human-readable name for error messages.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        return False, f"{description}: command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"{description}: timed out after {timeout}s"


def run_lint() -> tuple[bool, str]:
    """Run ruff lint check."""
    return _run_subprocess(["ruff", "check", "."], timeout=120, description="Lint")


def run_format_check() -> tuple[bool, str]:
    """Run ruff format check."""
    return _run_subprocess(["ruff", "format", "--check", "."], timeout=120, description="Format")


def run_typecheck() -> tuple[bool, str]:
    """Run mypy type check."""
    return _run_subprocess(
        [sys.executable, "-m", "mypy", "tools/scripts/", "--ignore-missing-imports"],
        timeout=120,
        description="Type check",
    )


def run_tests() -> tuple[bool, str]:
    """Run pytest test suite."""
    return _run_subprocess(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--cov=tools/scripts",
            "--cov-report=term-missing",
            "--tb=short",
        ],
        timeout=300,
        description="Tests",
    )


def run_security() -> tuple[bool, str]:
    """Run security scan (bandit + pip-audit)."""
    results: list[tuple[str, bool, str]] = []

    # bandit
    bandit_passed, bandit_out = _run_subprocess(
        [
            "bandit",
            "-r",
            "tools/scripts/",
            "-f",
            "json",
            "-o",
            "bandit-report.json",
            "-ll",
        ],
        timeout=120,
        description="Bandit",
    )
    results.append(("bandit", bandit_passed, bandit_out))

    # pip-audit
    audit_passed, audit_out = _run_subprocess(
        ["pip-audit", "--desc", "--timeout", "30"],
        timeout=120,
        description="pip-audit",
    )
    results.append(("pip-audit", audit_passed, audit_out))

    all_passed = all(r[1] for r in results)
    output = "\n".join(f"=== {r[0]} ===\n{r[2]}" for r in results)
    return all_passed, output


def run_lint_files(paths: list[str]) -> tuple[bool, str]:
    """Run ruff lint on specific files."""
    if not paths:
        return True, "No Python files to lint"
    return _run_subprocess(["ruff", "check", *paths], timeout=60, description="Lint")


def run_format_files(paths: list[str]) -> tuple[bool, str]:
    """Run ruff format check on specific files."""
    if not paths:
        return True, "No Python files to format-check"
    return _run_subprocess(["ruff", "format", "--check", *paths], timeout=60, description="Format")


# Registry of all basic check functions for discovery
BASIC_CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {
    "lint": run_lint,
    "format": run_format_check,
    "typecheck": run_typecheck,
    "test": run_tests,
    "security": run_security,
}
