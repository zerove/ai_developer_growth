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

# =============================================================================
# CLI
# =============================================================================


def main() -> int:
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

    # lint
    subparsers.add_parser("lint", help="Run ruff lint check")

    # format
    subparsers.add_parser("format", help="Run ruff format check")

    # typecheck
    subparsers.add_parser("typecheck", help="Run mypy type check")

    # test
    subparsers.add_parser("test", help="Run pytest test suite")

    # security
    subparsers.add_parser("security", help="Run security scan (bandit + pip-audit)")

    # language-rules
    lr_parser = subparsers.add_parser("language-rules", help="Run language-specific rules validation")
    lr_parser.add_argument("--path", type=Path, default=Path("."), help="Path to validate")
    lr_parser.add_argument("--lang", help="Language (auto-detect if not specified)")

    # quality-gate
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

    # governance-audit
    ga_parser = subparsers.add_parser("governance-audit", help="Run Governance Auditor checks")
    ga_parser.add_argument("--full", action="store_true", help="Run all governance checks")
    ga_parser.add_argument("--validate-docs", action="store_true", help="Validate governance docs")
    ga_parser.add_argument("--check-ai-sdlc", action="store_true", help="Check AI-SDLC compliance")
    ga_parser.add_argument("--audit-hallucination", action="store_true", help="Audit hallucination risks")
    ga_parser.add_argument("--check-index", action="store_true", help="Check index references")

    # diff (incremental)
    diff_parser = subparsers.add_parser("diff", help="Incremental check: only changed files vs base ref")
    diff_parser.add_argument("--base", default="HEAD", help="Git ref to diff against (default: HEAD)")

    # pre-commit
    subparsers.add_parser("pre-commit", help="Pre-commit hook: check staged files only")

    # full
    subparsers.add_parser(
        "full", help="Run all checks (lint, format, typecheck, test, security, quality-gate, governance-audit)"
    )

    args = parser.parse_args()

    # Dispatch commands
    if args.command == "lint":
        passed, output = run_lint()
        print(output)
        return 0 if passed else 1

    elif args.command == "format":
        passed, output = run_format_check()
        print(output)
        return 0 if passed else 1

    elif args.command == "typecheck":
        passed, output = run_typecheck()
        print(output)
        return 0 if passed else 1

    elif args.command == "test":
        passed, output = run_tests()
        print(output)
        return 0 if passed else 1

    elif args.command == "security":
        passed, output = run_security()
        print(output)
        return 0 if passed else 1

    elif args.command == "language-rules":
        passed, output = run_language_rules(args.path, args.lang)
        print(output)
        return 0 if passed else 1

    elif args.command == "quality-gate":
        passed, output = run_quality_gate(
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
        print(output)
        return 0 if passed else 1

    elif args.command == "governance-audit":
        passed, output = run_governance_audit(
            full=args.full,
            validate_docs=args.validate_docs,
            check_ai_sdlc=args.check_ai_sdlc,
            audit_hallucination=args.audit_hallucination,
            check_index=args.check_index,
        )
        print(output)
        return 0 if passed else 1

    elif args.command == "diff":
        passed, output = run_diff_checks(args.base)
        print(output)
        return 0 if passed else 1

    elif args.command == "pre-commit":
        passed, output = run_pre_commit_checks()
        print(output)
        return 0 if passed else 1

    elif args.command == "full":
        print("=" * 60)
        print("  FULL HOOKS RUNNER - 完整检查套件")
        print("=" * 60)

        # 并行执行独立检查 (lint + format + typecheck 可并行)
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

        # 串行执行有依赖的检查
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

        # 输出结果 (按固定顺序)
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

    # Unknown command
    print(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
