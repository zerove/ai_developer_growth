"""Hooks runner: 检查阶段编排域（P2-1 第五刀）。

phase 调度、并行执行、full 流程与 semantic/ast-fix/hallucination 命令。
由 hooks_runner.py import 转发。
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

from tools.scripts.hooks.tool_runner import (
    _detect_project_languages,
    _parse_languages,
)
from tools.scripts.language_registry import Language

logger = logging.getLogger(__name__)


def _resolve_alias(name: str) -> Callable[..., Any]:
    """延迟解析 hooks_runner 的别名函数（保持测试可 patch 主模块符号）。"""
    from tools.scripts import hooks_runner

    func: Callable[..., Any] = getattr(hooks_runner, name)
    return func


def _run_lint_phase() -> tuple[bool, str]:
    result: tuple[bool, str] = _resolve_alias("run_lint")()
    return result


def _run_format_phase() -> tuple[bool, str]:
    result: tuple[bool, str] = _resolve_alias("run_format_check")()
    return result


def _run_typecheck_phase() -> tuple[bool, str]:
    result: tuple[bool, str] = _resolve_alias("run_typecheck")()
    return result


def _run_test_phase() -> tuple[bool, str]:
    result: tuple[bool, str] = _resolve_alias("run_tests")()
    return result


def _run_security_phase() -> tuple[bool, str]:
    result: tuple[bool, str] = _resolve_alias("run_security")()
    return result


def _run_quality_gate_full() -> tuple[bool, str]:
    """全量质量门禁检查（经 hooks_runner 延迟解析，保持测试可 patch）。"""
    func = _resolve_alias("run_quality_gate")
    result: tuple[bool, str] = func(_full_path, full=True)
    return result


def _run_governance_audit_full() -> tuple[bool, str]:
    """全量治理审计（经 hooks_runner 延迟解析，保持测试可 patch）。"""
    func = _resolve_alias("run_governance_audit")
    result: tuple[bool, str] = func(full=True)
    return result


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
    _, phase_index = _load_phase_tables()
    func_name, parallel, _ = phase_index[phase_name]
    _ = parallel  # 依赖解析阶段由 _run_full 统一调度并行
    print(f"⏳ [hooks] 阶段开始: {phase_name}", flush=True)
    start = time.monotonic()
    try:
        passed, output = _resolve_phase_func(func_name)()
    except Exception as e:
        passed, output = False, str(e)
    elapsed = time.monotonic() - start
    status = "✅" if passed else "❌"
    print(f"{status} [hooks] 阶段完成: {phase_name} ({elapsed:.1f}s)", flush=True)
    results[phase_name] = (passed, output)


def _resolve_order() -> list[str]:
    """拓扑排序所有阶段，保证依赖先于使用者执行。"""
    order: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        _, _, deps = phase_index[name]
        for dep in deps:
            if dep in phase_index:
                visit(dep)
        order.append(name)

    _, phase_index = _load_phase_tables()
    for name in phase_index:
        visit(name)
    return order


_full_args: argparse.Namespace | None = None
_full_path: Path = Path(".")
_full_langs: list[Language] = []


def _load_phase_tables() -> tuple[list[tuple[str, str, bool, list[str]]], dict[str, tuple[str, bool, list[str]]]]:
    """延迟加载阶段表（保持 hooks_runner 主模块对测试的可 mock 性）。"""
    from tools.scripts import hooks_runner

    return hooks_runner._CHECK_PHASES, hooks_runner._PHASE_INDEX


def _run_parallel_checks() -> dict[str, tuple[bool, str]]:
    """Run parallel phase checks: lint, format, typecheck."""
    check_phases, _ = _load_phase_tables()
    parallel_phases = [name for name, _, parallel, _ in check_phases if parallel]
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=len(parallel_phases)) as executor:
        futures = {
            executor.submit(_resolve_phase_func(func_name)): name
            for name, func_name, parallel, _ in check_phases
            if name in parallel_phases and parallel
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                passed, output = future.result()
            except Exception as e:
                passed, output = False, str(e)
            status = "✅" if passed else "❌"
            print(f"{status} [hooks] 并行阶段完成: {name}", flush=True)
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


def _run_sequential_phases(results: dict[str, tuple[bool, str]]) -> None:
    """执行串行阶段 (含依赖解析: 依赖失败则跳过)。"""
    check_phases, phase_index = _load_phase_tables()
    sequential_phases = [name for name, _, parallel, _ in check_phases if not parallel]
    for name in sequential_phases:
        _, _, deps = phase_index[name]
        passed_deps = True
        failed_deps: list[str] = []
        for dep in deps:
            if dep not in results:
                _run_phase(dep, results)
            if not results[dep][0]:
                passed_deps = False
                failed_deps.append(dep)
        if passed_deps:
            _run_phase(name, results)
        else:
            results[name] = (False, f"Skipped: dependency '{failed_deps}' failed")


def _run_full(args: argparse.Namespace) -> int:
    """Run the full check suite with parallel + sequential phases."""
    global _full_args, _full_langs, _full_path

    _full_args = args
    _full_path = args.path

    # 检测语言
    if args.lang:
        _full_langs = _parse_languages(args.lang)
    else:
        _full_langs = _detect_project_languages(args.path)

    if not _full_langs:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        _full_langs = [Language.PYTHON]

    print("=" * 60)
    print("  FULL HOOKS RUNNER - 完整检查套件 (多语言)")
    print(f"  检测语言: {', '.join(lang.value for lang in _full_langs)}")
    print(f"  项目路径: {_full_path}")
    print("=" * 60)

    results: dict[str, tuple[bool, str]] = {}
    results.update(_run_parallel_checks())
    _run_sequential_phases(results)

    order = _resolve_order()
    all_passed = _print_results_in_order(results, order)

    print("\n" + "=" * 60)
    print("✅ ALL CHECKS PASSED" if all_passed else "❌ SOME CHECKS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


def _run_semantic_check(path: Path, lang: str | None, jobs: int) -> int:
    """Run AST-based semantic analysis on a directory or file."""
    from tools.scripts.rules_engine.checker import check_directory, check_file

    print("=" * 60)
    print("  SEMANTIC CHECK (tree-sitter AST)")
    print("=" * 60)

    if path.is_file():
        result = check_file(path, semantic=True)
        from tools.scripts.hooks_runner import _print_check_result

        _print_check_result(result)
        return 0 if not result.issues else 1

    languages = [lang] if lang else None
    results = check_directory(path, languages=languages, jobs=jobs, semantic=True)

    total_issues = 0
    for result in sorted(results, key=lambda r: r.file):
        from tools.scripts.hooks_runner import _print_check_result

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
