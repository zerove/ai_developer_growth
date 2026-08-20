"""增量检查函数: diff, pre-commit, git helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.scripts.hooks.basic_checks import (
    INCREMENTAL_EXTENSIONS,
    run_format_files,
    run_lint_files,
)
from tools.scripts.validate_language_rules import (
    detect_language_from_file,
    validate_file,
)


def get_changed_files(base: str = "HEAD") -> list[Path]:
    """Get list of changed files compared to a base ref (git diff).

    Args:
        base: Git ref to diff against.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Fallback: try diff with main/master
            for ref in ["origin/main", "origin/master", "main", "master"]:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=ACMR", ref],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    break

        return [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_staged_files() -> list[Path]:
    """Get list of files staged for commit (git diff --cached)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _check_code_files(
    code_files: list[Path],
    *,
    label: str,
) -> tuple[bool, str]:
    """Run lint, format, and language-rule checks on a list of code files.

    Args:
        code_files: List of code files to check.
        label: Human-readable label for output (e.g. "changed" or "staged").
    """
    output_lines: list[str] = [f"{label}: checking {len(code_files)} file(s)...\n"]
    all_passed = True

    # Lint + format on Python files
    py_files = [str(f) for f in code_files if f.suffix == ".py"]
    if py_files:
        lint_passed, lint_out = run_lint_files(py_files)
        if not lint_passed:
            output_lines.append(f"❌ Lint errors:\n{lint_out}")
            all_passed = False

        fmt_passed, fmt_out = run_format_files(py_files)
        if not fmt_passed:
            output_lines.append(
                f"❌ Format errors (run: ruff format {py_files[0]} ...):\n{fmt_out}"
            )
            all_passed = False

    # Language rules on all code files
    for filepath in code_files:
        lang = detect_language_from_file(filepath)
        if lang:
            result = validate_file(filepath, lang)
            if not result.passed:
                output_lines.append(f"❌ {filepath}: {len(result.issues)} violations")
                all_passed = False

    if all_passed:
        output_lines.insert(0, f"✅ All {len(code_files)} {label} files pass checks")

    return all_passed, "\n".join(output_lines)


def run_diff_checks(base: str = "HEAD") -> tuple[bool, str]:
    """Run checks only on changed files vs a base ref.

    Args:
        base: Git ref to diff against.
    """
    changed = get_changed_files(base)
    if not changed:
        return True, "No changed files detected"

    code_files = [
        f for f in changed if f.suffix in INCREMENTAL_EXTENSIONS and f.exists()
    ]

    if not code_files:
        return True, f"No code files in {len(changed)} changed files"

    return _check_code_files(code_files, label="Changed")


def run_pre_commit_checks() -> tuple[bool, str]:
    staged = get_staged_files()
    if not staged:
        return True, "No staged files"

    code_files = [
        f for f in staged if f.suffix in INCREMENTAL_EXTENSIONS and f.exists()
    ]

    if not code_files:
        return True, f"No code files in {len(staged)} staged files"

    passed, output = _check_code_files(code_files, label="Staged")

    try:
        from tools.scripts.audit_attestation import AuditAttestationLedger
        from tools.scripts.hooks.scope_guard import ScopeGuardHook

        root = Path(__file__).resolve().parent.parent.parent
        scope_ok, scope_msg = ScopeGuardHook(root_dir=root).check_git_diff()
        AuditAttestationLedger(root).record_trace(
            "PRE_COMMIT_HOOK", {"staged_count": len(staged), "scope_passed": scope_ok}
        )
        if not scope_ok:
            passed = False
            output += f"\n🛡️ {scope_msg}"
        else:
            output += f"\n🛡️ {scope_msg}"
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(f"Pre-commit scope check failed: {e}")

    return passed, output
