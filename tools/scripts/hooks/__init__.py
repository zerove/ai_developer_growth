"""hooks package - Modular hook system for the rules engine.

Submodules:
    basic_checks: Lint, format, typecheck, test, security runners.
    domain_checks: Language-rules, quality-gate, governance-audit runners.
    incremental_checks: Diff-based and pre-commit check runners.
"""

from tools.scripts.hooks.basic_checks import (
    BASIC_CHECKS,
    CODE_EXTENSIONS,
    INCREMENTAL_EXTENSIONS,
    run_format_check,
    run_format_files,
    run_lint,
    run_lint_files,
    run_security,
    run_tests,
    run_typecheck,
)
from tools.scripts.hooks.domain_checks import (
    run_governance_audit,
    run_language_rules,
    run_quality_gate,
)
from tools.scripts.hooks.incremental_checks import (
    get_changed_files,
    get_staged_files,
    run_diff_checks,
    run_pre_commit_checks,
)

__all__ = [
    # Basic checks
    "BASIC_CHECKS",
    "CODE_EXTENSIONS",
    "INCREMENTAL_EXTENSIONS",
    "run_lint",
    "run_format_check",
    "run_typecheck",
    "run_tests",
    "run_security",
    "run_lint_files",
    "run_format_files",
    # Domain checks
    "run_language_rules",
    "run_quality_gate",
    "run_governance_audit",
    # Incremental checks
    "get_changed_files",
    "get_staged_files",
    "run_diff_checks",
    "run_pre_commit_checks",
]
