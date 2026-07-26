#!/usr/bin/env python3
"""
统一 Hook 运行器 (CLI 入口)

模块化拆分:
    - hooks/basic_checks.py    : lint, format, typecheck, test, security
    - hooks/domain_checks.py   : language-rules, quality-gate, governance-audit
    - hooks/incremental_checks.py : diff, pre-commit, git helpers

用法:
    python hooks_runner.py lint
    python hooks_runner.py format
    python hooks_runner.py typecheck
    python hooks_runner.py test
    python hooks_runner.py security
    python hooks_runner.py language-rules [--path PATH] [--lang LANG]
    python hooks_runner.py quality-gate [--path PATH] [--full] [--check-security] ...
    python hooks_runner.py governance-audit [--full] [--validate-docs] [--check-ai-sdlc] [--audit-hallucination]
    python hooks_runner.py diff [--base REF]  # Incremental: only check changed files
    python hooks_runner.py pre-commit        # Pre-commit hook: check staged files
    python hooks_runner.py full
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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
from tools.scripts.hooks.incremental_checks import (  # noqa: F401
    get_changed_files,
    get_staged_files,
    run_diff_checks,
    run_pre_commit_checks,
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="统一 Hook 运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hooks_runner.py lint
  hooks_runner.py format
  hooks_runner.py typecheck
  hooks_runner.py test
  hooks_runner.py security
  hooks_runner.py language-rules --path tools/scripts --lang python
  hooks_runner.py quality-gate --path tools/scripts --full
  hooks_runner.py governance-audit --full
  hooks_runner.py full
        """,
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
    lr_parser.add_argument("--jobs", "-j", type=int, default=1, help="Parallel workers (default: 1)")
    lr_parser.add_argument("--fix", action="store_true", help="Apply auto-fixes to fixable issues")

    qg_parser = subparsers.add_parser("quality-gate", help="Run AI Quality Gate checks")
    qg_parser.add_argument("--path", type=Path, default=Path("tools/scripts"), help="Path to check")
    qg_parser.add_argument("--full", action="store_true", help="Run all checks")
    qg_parser.add_argument("--check-annotation", action="store_true", help="Check AI annotation")
    qg_parser.add_argument("--check-security", action="store_true", help="Check security patterns")
    qg_parser.add_argument("--check-type", action="store_true", help="Check type safety")
    qg_parser.add_argument("--check-error", action="store_true", help="Check error handling")
    qg_parser.add_argument("--check-structure", action="store_true", help="Check code structure")
    qg_parser.add_argument("--check-patterns", action="store_true", help="Check all anti-patterns")
    qg_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    ga_parser = subparsers.add_parser("governance-audit", help="Run Governance Auditor checks")
    ga_parser.add_argument("--full", action="store_true", help="Run all governance checks")
    ga_parser.add_argument("--validate-docs", action="store_true", help="Validate governance docs")
    ga_parser.add_argument("--check-ai-sdlc", action="store_true", help="Check AI-SDLC compliance")
    ga_parser.add_argument("--audit-hallucination", action="store_true", help="Audit hallucination risks")
    ga_parser.add_argument("--check-index", action="store_true", help="Check index references")

    diff_parser = subparsers.add_parser("diff", help="Incremental check: only changed files vs base ref")
    diff_parser.add_argument("--base", default="HEAD", help="Git ref to diff against (default: HEAD)")

    subparsers.add_parser("pre-commit", help="Pre-commit hook: check staged files only")

    install_parser = subparsers.add_parser("install-hooks", help="Install git hooks")
    install_parser.add_argument("--pre-push", action="store_true", help="Install pre-push hook")
    install_parser.add_argument("--pre-commit", action="store_true", help="Install pre-commit hook")

    learn_parser = subparsers.add_parser("learn", help="AI-driven rule generation from codebase analysis")
    learn_parser.add_argument(
        "project_path", type=Path, nargs="?", default=Path("."), help="Project root (default: current dir)"
    )
    learn_parser.add_argument("--output", "-o", type=Path, help="Output rules YAML file")
    learn_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    dashboard_parser = subparsers.add_parser("dashboard", help="Start quality dashboard web server")
    dashboard_parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    dashboard_parser.add_argument("--db", default="adg_quality.db", help="SQLite database path")

    subparsers.add_parser(
        "full", help="Run all checks (lint, format, typecheck, test, security, quality-gate, governance-audit)"
    )

    return parser


def _run_simple(func_or_result: Any) -> int:
    """Run a simple check function and print output.

    Accepts either:
    - A callable that returns (bool, str)
    - An already-evaluated (bool, str) tuple
    """
    if callable(func_or_result):
        passed, output = func_or_result()
    else:
        passed, output = func_or_result
    print(output)
    return 0 if passed else 1


def _run_full() -> int:
    """Run the full check suite with parallel + sequential phases."""
    print("=" * 60)
    print("  FULL HOOKS RUNNER - 完整检查套件")
    print("=" * 60)

    # Parallel phase: lint + format + typecheck
    check_funcs = [
        ("Lint", run_lint),
        ("Format", run_format_check),
        ("Type Check", run_typecheck),
    ]
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(func): name for name, func in check_funcs}
        for future in as_completed(futures):
            name = futures[future]
            try:
                passed, output = future.result()
            except Exception as e:
                passed, output = False, str(e)
            results[name] = (passed, output)

    # Sequential phase: dependent checks
    sequential_checks = [
        ("Test Suite", run_tests),
        ("Security Scan", run_security),
        ("AI Quality Gate", lambda: run_quality_gate(Path("tools/scripts"), full=True)),
        ("Governance Audit", lambda: run_governance_audit(full=True)),
    ]
    for name, func in sequential_checks:
        try:
            passed, output = func()
        except Exception as e:
            passed, output = False, str(e)
        results[name] = (passed, output)

    # Print results in fixed order
    order = ["Lint", "Format", "Type Check", "Test Suite", "Security Scan", "AI Quality Gate", "Governance Audit"]
    all_passed = True
    for i, name in enumerate(order, 1):
        print(f"\n📋 {i}/7: {name}")
        passed, output = results[name]
        print(output)
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
    else:
        print("❌ SOME CHECKS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


# Dispatch table: command -> (func, needs_args)
_SIMPLE_COMMANDS = {
    "lint": run_lint,
    "format": run_format_check,
    "typecheck": run_typecheck,
    "test": run_tests,
    "security": run_security,
}


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch the parsed command to the appropriate handler."""
    cmd = args.command

    if cmd in _SIMPLE_COMMANDS:
        return _run_simple(_SIMPLE_COMMANDS[cmd])

    if cmd == "language-rules":
        if getattr(args, "fix", False):
            from tools.scripts.rules_engine.auto_fix import apply_fixes_to_directory, format_fix_results

            fix_results = apply_fixes_to_directory(args.path, dry_run=False)
            print(format_fix_results(fix_results))
            return 0
        return _run_simple(run_language_rules(args.path, args.lang))

    if cmd == "quality-gate":
        return _run_simple(
            run_quality_gate(
                args.path,
                full=args.full,
                check_annotation=args.check_annotation,
                check_security=args.check_security,
                check_type=args.check_type,
                check_error=args.check_error,
                check_structure=args.check_structure,
                check_patterns=args.check_patterns,
                format=args.format,
            )
        )

    if cmd == "governance-audit":
        return _run_simple(
            run_governance_audit(
                full=args.full,
                validate_docs=args.validate_docs,
                check_ai_sdlc=args.check_ai_sdlc,
                audit_hallucination=args.audit_hallucination,
                check_index=args.check_index,
            )
        )

    if cmd == "diff":
        return _run_simple(run_diff_checks(args.base))

    if cmd == "pre-commit":
        return _run_simple(run_pre_commit_checks())

    if cmd == "install-hooks":
        if args.pre_push:
            from tools.scripts.hooks.pre_push import install_pre_push_hook

            success = install_pre_push_hook()
            return 0 if success else 1
        if args.pre_commit:
            print("Pre-commit hook installation not yet implemented")
            return 1
        print("Specify --pre-push or --pre-commit")
        return 1

    if cmd == "learn":
        from tools.scripts.rules_engine.ai_rules_generator import (
            analyze_project,
            format_analysis,
        )

        result = analyze_project(args.project_path)
        print(format_analysis(result, format=args.format))
        if args.output:
            import yaml

            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                yaml.dump(result["rules"], f, default_flow_style=False, allow_unicode=True)
            print(f"\nRules written to {args.output}")
        return 0

    if cmd == "dashboard":
        import uvicorn

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(args.db)
        print(f"Starting ADG Quality Dashboard at http://0.0.0.0:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
        return 0

    if cmd == "full":
        return _run_full()

    print(f"Unknown command: {cmd}")
    return 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
