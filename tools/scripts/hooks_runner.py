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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import cast

# 阶段函数通过名称字符串运行时解析（_CHECK_PHASES / _resolve_phase_func），
# 必须在模块命名空间中存在，故 noqa: F401
from tools.scripts.hooks.basic_checks import (  # noqa: F401
    run_format_check,
    run_lint,
    run_security,
    run_tests,
    run_typecheck,
)
from tools.scripts.hooks.domain_checks import (  # noqa: F401
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
from tools.scripts.rules_engine.models import CheckResult


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
    lr_parser.add_argument("--cache", action="store_true", help="启用增量缓存（复用检查历史）")
    lr_parser.add_argument("--db", default="adg_quality.db", help="统一存储数据库路径（默认 adg_quality.db）")

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

    sc_parser = subparsers.add_parser("semantic-check", help="Run AST-based semantic analysis (tree-sitter)")
    sc_parser.add_argument("--path", type=Path, default=Path("."), help="Path to check")
    sc_parser.add_argument("--lang", help="Language filter")
    sc_parser.add_argument("--jobs", "-j", type=int, default=1, help="Parallel workers")

    af_parser = subparsers.add_parser("ast-fix", help="Run AST-based auto-fix on files")
    af_parser.add_argument("--path", type=Path, default=Path("."), help="Path to fix")
    af_parser.add_argument("--dry-run", action="store_true", help="Preview fixes without applying")

    hs_parser = subparsers.add_parser("hallucination-scan", help="Scan for AI hallucination patterns in code")
    hs_parser.add_argument("--path", type=Path, default=Path("."), help="Path to scan")
    hs_parser.add_argument("--lang", help="Language filter")

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


def _run_simple(func_or_result: Callable[[], tuple[bool, str]] | tuple[bool, str]) -> int:
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


def _run_semantic_check(path: Path, lang: str | None, jobs: int) -> int:
    """Run AST-based semantic analysis on a directory or file."""
    from tools.scripts.rules_engine.checker import check_directory, check_file

    print("=" * 60)
    print("  SEMANTIC CHECK (tree-sitter AST)")
    print("=" * 60)

    if path.is_file():
        result = check_file(path, semantic=True)
        _print_check_result(result)
        return 0 if not result.issues else 1

    languages = [lang] if lang else None
    results = check_directory(path, languages=languages, jobs=jobs, semantic=True)

    total_issues = 0
    for result in sorted(results, key=lambda r: r.file):
        _print_check_result(result)
        total_issues += len(result.issues)

    print(f"\n{'=' * 60}")
    print(f"  Scanned {len(results)} files, found {total_issues} semantic issues")
    if total_issues == 0:
        print("  ✅ ALL CLEAN")
    else:
        print("  ⚠️  Issues found")
    print("=" * 60)

    return 0 if total_issues == 0 else 1


def _run_ast_fix(path: Path, dry_run: bool) -> int:
    """Run AST-based auto-fix on files."""
    from tools.scripts.rules_engine.ast_fixer import ASTFixer

    print("=" * 60)
    print("  AST AUTO-FIX" + (" (dry run)" if dry_run else ""))
    print("=" * 60)

    fixer = ASTFixer()

    if path.is_file():
        report = fixer.fix_file(path, dry_run=dry_run)
        if report is None:
            print(f"  ⚠️  Cannot parse {path}, skipping")
            return 0
        print(fixer.format_fix_report(report))
        return 0 if report.total_fixes == 0 else (0 if dry_run else 1)

    # Directory: fix all Python files
    total_fixes = 0
    for filepath in sorted(path.rglob("*.py")):
        if any(d in filepath.parts for d in {"__pycache__", ".git", "node_modules", ".venv"}):
            continue
        report = fixer.fix_file(filepath, dry_run=dry_run)
        if report is None:
            continue
        if report.total_fixes > 0:
            print(fixer.format_fix_report(report))
            total_fixes += report.total_fixes

    print(f"\n{'=' * 60}")
    print(f"  Total fixes: {total_fixes}" + (" (dry run)" if dry_run else ""))
    if total_fixes == 0:
        print("  ✅ No fixes needed")
    elif dry_run:
        print("  ℹ️  Run without --dry-run to apply")
    else:
        print("  ✅ Fixes applied")
    print("=" * 60)

    return 0


def _run_hallucination_scan(path: Path, lang: str | None) -> int:
    """Run AI hallucination pattern detection."""
    from tools.scripts.rules_engine.hallucination_detector import (
        detect_hallucinations,
        detect_hallucinations_in_file,
        format_hallucination_report,
    )

    print("=" * 60)
    print("  AI HALLUCINATION PATTERN SCAN")
    print("=" * 60)

    if path.is_file():
        report = detect_hallucinations_in_file(path)
    else:
        report = detect_hallucinations(path)

    print(format_hallucination_report(report))

    return 0 if report.high_count == 0 else 1


def _print_check_result(result: CheckResult) -> None:
    """Print a single check result if it has issues."""
    if result.issues:
        for issue in result.issues:
            severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "?")
            print(f"  {severity_icon} {result.file}:{issue.line} [{issue.rule_id}] {issue.message}")


# ─── 检查阶段数据定义 ──────────────────────────────────────
# 每个阶段: (名称, 函数名, 是否可并行, 依赖阶段)
# 依赖阶段: 本阶段开始前必须已完成的阶段名列表
# 函数名在运行时通过 globals() 解析，便于测试 mock 与配置化扩展
_CHECK_PHASES: list[tuple[str, str, bool, list[str]]] = [
    ("Lint", "run_lint", True, []),
    ("Format", "run_format_check", True, []),
    ("Type Check", "run_typecheck", True, []),
    ("Test Suite", "run_tests", False, ["Type Check"]),
    ("Security Scan", "run_security", False, ["Test Suite"]),
    ("AI Quality Gate", "_run_quality_gate_full", False, ["Type Check"]),
    ("Governance Audit", "_run_governance_audit_full", False, []),
]

# 阶段名到 (函数名, 并行标记, 依赖) 的索引
_PHASE_INDEX: dict[str, tuple[str, bool, list[str]]] = {
    name: (func_name, parallel, deps) for name, func_name, parallel, deps in _CHECK_PHASES
}


def _run_quality_gate_full() -> tuple[bool, str]:
    """全量质量门禁检查（阶段用具名函数便于运行时解析与 mock）。"""
    return run_quality_gate(Path("tools/scripts"), full=True)


def _run_governance_audit_full() -> tuple[bool, str]:
    """全量治理审计（阶段用具名函数）。"""
    return run_governance_audit(full=True)


def _resolve_phase_func(func_name: str) -> Callable[[], tuple[bool, str]]:
    """运行时解析阶段函数（支持测试 mock 与外部配置）。"""
    func = globals().get(func_name, None)
    if not callable(func):
        raise NameError(f"阶段函数未定义: {func_name}")
    return cast(Callable[[], tuple[bool, str]], func)


def _run_phase(phase_name: str, results: dict[str, tuple[bool, str]]) -> None:
    """执行单个阶段并记录结果（跳过已执行阶段）。"""
    if phase_name in results:
        return
    func_name, parallel, _ = _PHASE_INDEX[phase_name]
    _ = parallel  # 依赖解析阶段由 _run_full 统一调度并行
    try:
        passed, output = _resolve_phase_func(func_name)()
    except Exception as e:
        passed, output = False, str(e)
    results[phase_name] = (passed, output)


def _resolve_order() -> list[str]:
    """拓扑排序所有阶段，保证依赖先于使用者执行。"""
    order: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        _, _, deps = _PHASE_INDEX[name]
        for dep in deps:
            if dep in _PHASE_INDEX:
                visit(dep)
        order.append(name)

    for name in _PHASE_INDEX:
        visit(name)
    return order


def _run_parallel_checks() -> dict[str, tuple[bool, str]]:
    """Run parallel phase checks: lint, format, typecheck."""
    parallel_phases = [name for name, _, parallel, _ in _CHECK_PHASES if parallel]
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=len(parallel_phases)) as executor:
        futures = {
            executor.submit(_resolve_phase_func(func_name)): name
            for name, func_name, parallel, _ in _CHECK_PHASES
            if name in parallel_phases and parallel  # 仅并行标记为真的阶段进入线程池（防御性检查）
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                passed, output = future.result()
            except Exception as e:
                passed, output = False, str(e)
            results[name] = (passed, output)
    return results


def _print_results_in_order(results: dict[str, tuple[bool, str]], order: list[str]) -> bool:
    """Print results in fixed order. Returns all_passed."""
    all_passed = True
    for i, name in enumerate(order, 1):
        print(f"\n📋 {i}/{len(order)}: {name}")
        passed, output = results[name]
        print(output)
        if not passed:
            all_passed = False
    return all_passed


def _run_full() -> int:
    """Run the full check suite with parallel + sequential phases."""
    print("=" * 60)
    print("  FULL HOOKS RUNNER - 完整检查套件")
    print("=" * 60)

    results: dict[str, tuple[bool, str]] = {}
    results.update(_run_parallel_checks())

    # 串行阶段（含依赖解析）
    sequential_phases = [name for name, _, parallel, _ in _CHECK_PHASES if not parallel]
    for name in sequential_phases:
        passed_deps = True
        _, _, deps = _PHASE_INDEX[name]
        for dep in deps:
            if dep not in results:
                _run_phase(dep, results)
            if not results[dep][0]:
                passed_deps = False
        if passed_deps:
            _run_phase(name, results)
        else:
            results[name] = (
                False,
                f"Skipped: dependency '{[d for d in deps if d not in results or not results[d][0]]}' failed",
            )

    order = _resolve_order()
    all_passed = _print_results_in_order(results, order)

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
    else:
        print("❌ SOME CHECKS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


# Dispatch table: command -> function name (lazy lookup for mockability)
_SIMPLE_COMMANDS: dict[str, str] = {
    "lint": "run_lint",
    "format": "run_format_check",
    "typecheck": "run_typecheck",
    "test": "run_tests",
    "security": "run_security",
}


def _handle_language_rules(args: argparse.Namespace) -> int:
    """Handle language-rules command."""
    if getattr(args, "fix", False):
        from tools.scripts.rules_engine.auto_fix import apply_fixes_to_directory, format_fix_results

        fix_results = apply_fixes_to_directory(args.path, dry_run=False)
        print(format_fix_results(fix_results))
        return 0
    if getattr(args, "cache", False):
        # 增量缓存模式：复用统一存储中的检查历史（mtime+size 未变则跳过）
        from tools.scripts.rules_engine.checker import check_directory

        results = check_directory(args.path, jobs=getattr(args, "jobs", 1), use_cache=True, db_path=args.db)
        passed = all(r.passed for r in results)
        lines = [f"{r.file}: {'PASS' if r.passed else 'FAIL'} ({len(r.issues)} issues)" for r in results]
        print("\n".join(lines) if lines else "No files to check")
        return 0 if passed else 1
    return _run_simple(run_language_rules(args.path, args.lang))


def _handle_quality_gate(args: argparse.Namespace) -> int:
    """Handle quality-gate command."""
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


def _handle_governance_audit(args: argparse.Namespace) -> int:
    """Handle governance-audit command."""
    return _run_simple(
        run_governance_audit(
            full=args.full,
            validate_docs=args.validate_docs,
            check_ai_sdlc=args.check_ai_sdlc,
            audit_hallucination=args.audit_hallucination,
            check_index=args.check_index,
        )
    )


def _handle_install_hooks(args: argparse.Namespace) -> int:
    """Handle install-hooks command."""
    if args.pre_push:
        from tools.scripts.hooks.pre_push import install_pre_push_hook

        success = install_pre_push_hook()
        return 0 if success else 1
    if args.pre_commit:
        print("Pre-commit hook installation not yet implemented")
        return 1
    print("Specify --pre-push or --pre-commit")
    return 1


def _handle_learn(args: argparse.Namespace) -> int:
    """Handle learn command."""
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


def _handle_dashboard(args: argparse.Namespace) -> int:
    """Handle dashboard command."""
    import uvicorn

    from tools.scripts.rules_engine.dashboard import create_app

    app = create_app(args.db)
    print(f"Starting ADG Quality Dashboard at http://0.0.0.0:{args.port}")  # nosec - dev only
    uvicorn.run(app, host="0.0.0.0", port=args.port)  # nosec - dev only
    return 0


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch the parsed command to the appropriate handler."""
    cmd = args.command

    if cmd in _SIMPLE_COMMANDS:
        func = globals()[_SIMPLE_COMMANDS[cmd]]
        return _run_simple(func)

    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "language-rules": _handle_language_rules,
        "quality-gate": _handle_quality_gate,
        "governance-audit": _handle_governance_audit,
        "diff": lambda a: _run_simple(run_diff_checks(a.base)),
        "pre-commit": lambda a: _run_simple(run_pre_commit_checks()),
        "semantic-check": lambda a: _run_semantic_check(a.path, getattr(a, "lang", None), getattr(a, "jobs", 1)),
        "ast-fix": lambda a: _run_ast_fix(a.path, getattr(a, "dry_run", False)),
        "hallucination-scan": lambda a: _run_hallucination_scan(
            getattr(a, "path", Path(".")),
            getattr(a, "lang", None),
        ),
        "install-hooks": _handle_install_hooks,
        "learn": _handle_learn,
        "dashboard": _handle_dashboard,
        "full": lambda a: _run_full(),
    }

    handler = handlers.get(cmd)
    if handler:
        return handler(args)

    print(f"Unknown command: {cmd}")
    return 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
