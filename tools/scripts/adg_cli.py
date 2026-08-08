#!/usr/bin/env python3
"""
ADG (AI Developer Governance) Unified CLI Entry Point

Consolidates hooks, language rule validation, quality gates, governance audit,
and rule catalog management into a single robust command-line interface.

Usage:
    python -m tools.scripts.adg_cli lint
    python -m tools.scripts.adg_cli format
    python -m tools.scripts.adg_cli typecheck
    python -m tools.scripts.adg_cli test
    python -m tools.scripts.adg_cli security
    python -m tools.scripts.adg_cli language-rules --path . --lang python
    python -m tools.scripts.adg_cli quality-gate --path tools/scripts --full
    python -m tools.scripts.adg_cli governance-audit --full
    python -m tools.scripts.adg_cli full
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.scripts.hooks.basic_checks import (
    run_format_check,
    run_lint,
    run_security,
    run_tests,
    run_typecheck,
)
from tools.scripts.hooks.domain_checks import (
    run_governance_audit,
    run_language_rules,
    run_quality_gate,
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        description="ADG (AI Developer Governance) Unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("lint", help="Run ruff lint check")
    subparsers.add_parser("format", help="Run ruff format check")
    subparsers.add_parser("typecheck", help="Run mypy type check")
    subparsers.add_parser("test", help="Run pytest test suite")
    subparsers.add_parser("security", help="Run security scan (bandit + pip-audit)")

    lr_parser = subparsers.add_parser("language-rules", help="Run language-specific rules validation")
    lr_parser.add_argument("--path", type=Path, default=Path("."), help="Path to validate")
    lr_parser.add_argument("--lang", help="Language (auto-detect if not specified)")
    lr_parser.add_argument("--jobs", "-j", type=int, default=1, help="Parallel workers")
    lr_parser.add_argument("--fix", action="store_true", help="Apply auto-fixes")

    qg_parser = subparsers.add_parser("quality-gate", help="Run AI Quality Gate checks")
    qg_parser.add_argument("--path", type=Path, default=Path("tools/scripts"), help="Path to check")
    qg_parser.add_argument("--full", action="store_true", help="Run all checks")

    ga_parser = subparsers.add_parser("governance-audit", help="Run Governance Auditor checks")
    ga_parser.add_argument("--full", action="store_true", help="Run all governance checks")
    ga_parser.add_argument("--validate-docs", action="store_true", help="Validate governance docs")

    subparsers.add_parser("full", help="Run full pipeline (lint, format, typecheck, test, quality-gate)")

    return parser


def _run_full_pipeline() -> bool:
    """Run the full ADG validation pipeline."""
    print("Running full ADG validation pipeline...")
    return (
        run_lint()
        and run_format_check()
        and run_typecheck()
        and run_tests()
        and run_quality_gate(Path("tools/scripts"), full=True)
    )


def _dispatch_command(args: argparse.Namespace) -> bool:
    """Dispatch to the appropriate command handler."""
    command_map = {
        "lint": lambda: run_lint(),
        "format": lambda: run_format_check(),
        "typecheck": lambda: run_typecheck(),
        "test": lambda: run_tests(),
        "security": lambda: run_security(),
        "language-rules": lambda: run_language_rules(args.path, args.lang, args.jobs, args.fix),
        "quality-gate": lambda: run_quality_gate(args.path, args.full),
        "governance-audit": lambda: run_governance_audit(args.full, args.validate_docs),
        "full": _run_full_pipeline,
    }
    return command_map.get(args.command, lambda: False)()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    success = _dispatch_command(args)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
