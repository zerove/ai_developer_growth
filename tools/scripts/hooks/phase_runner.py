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
from typing import Any, NamedTuple, cast

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

    # ADR-065: 路径不存在时必须显式失败, 不能让 check_directory 返回空列表
    # 后打印 "ALL CLEAN" —— 那是"检查了 0 个文件"的假绿灯, 与"检查通过"不可分辨。
    if not path.exists():
        print(f"❌ 路径不存在: {path}")
        return 1

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
    """Run AST-based auto-fix on files (V2.21 P5-69 拆分: 抽 _fix_single_file + _print_directory_summary)."""
    from tools.scripts.rules_engine.ast_fixer import ASTFixer

    print("=" * 60)
    print("  AST AUTO-FIX" + (" (dry run)" if dry_run else ""))
    print("=" * 60)

    fixer = ASTFixer()

    # ADR-065: 同 _run_semantic_check —— 路径不存在时 rglob 匹配 0 个文件,
    # 汇总会打印 "No fixes needed", 与"确实没有可修复项"不可分辨。
    if not path.exists():
        print(f"❌ 路径不存在: {path}")
        return 1

    if path.is_file():
        # ADR-066: 单文件路径此前 verbose 默认 False, 即便真的改了文件也只
        # 打印标题, 用户无从得知改了什么。这里改为始终打印明细 ——
        # 单文件是用户显式指定的操作, 没有"批量扫描需安静"的场景。
        # ADR-068: 单文件路径也要区分发现数与实际应用数, 否则在只有
        # report-only 规则时会对用户谎称已修复。退出码沿用 docs/api/cli.md
        # 既有的"auto-safe 修复数"约定 —— 该约定不随 dry_run 变化,
        # 实测旧实现按发现数返回, 会让"一个都没改"也返回非零。
        result = _fix_single_file(fixer, path, dry_run, verbose=True)
        violations = 1 if result.syntax_violation else 0
        _print_directory_summary(result.found, result.auto_safe, result.applied, dry_run, violations)
        return result.auto_safe

    # Directory: fix all Python files
    total_found = 0
    total_auto_safe = 0
    total_applied = 0
    syntax_violations = 0
    for filepath in sorted(path.rglob("*.py")):
        if any(d in filepath.parts for d in {"__pycache__", ".git", "node_modules", ".venv"}):
            continue
        result = _fix_single_file(fixer, filepath, dry_run, verbose=True)
        total_found += result.found
        total_auto_safe += result.auto_safe
        total_applied += result.applied
        if result.syntax_violation:
            syntax_violations += 1

    _print_directory_summary(total_found, total_auto_safe, total_applied, dry_run, syntax_violations)
    return 0


class FileFixResult(NamedTuple):
    """单文件修复的三个计数 (ADR-068) 与语法自检结论 (ADR-070).

    三个计数**可以互不相等**, 必须分开对待:

    - ``found``: 检出的可修复项总数
    - ``auto_safe``: 其中标记为可自动应用的项数 —— 这是
      ``docs/api/cli.md`` 约定的退出码语义, 且与 dry_run 无关
      (dry-run 下"将会应用多少"才是用户关心的数)
    - ``applied``: 实际改写了文本的项数。dry_run 时恒为 0;
      非 dry-run 时也可能小于 ``auto_safe`` —— 已实测的成因:
      report-only 规则 (ADR-067)、修复结果无法解析被拒写盘 (ADR-070)。
      ``_apply_fix`` 行号越界是**未观测路径** (Phase 45 全仓实测 0 次)

    ``syntax_violation`` 为 True 表示修复结果**无法解析、已拒绝写盘**
    (ADR-070)。此时 ``applied`` 必为 0, 而 ``auto_safe`` 仍可能 > 0 ——
    二者不等正是要告诉用户"本该自动修的没修成", 汇总必须显式呈现,
    否则又会退回"报告成功、磁盘未改"的假绿灯。

    此前 CLI 只向上传递 ``found``, 却拿它打印 "✅ Fixes applied"
    并作为退出码 —— 三种含义被压缩成一个数, 是 ADR-068 的根因。
    """

    found: int
    auto_safe: int
    applied: int
    syntax_violation: bool = False
    syntax_error: str | None = None


def _fix_single_file(fixer: Any, filepath: Path, dry_run: bool, *, verbose: bool = False) -> FileFixResult:
    """单文件 AST 修复 (模块级 helper, 返回 FileFixResult).

    ADR-068: 此前返回单个 ``total_fixes``（**发现数**）, 而
    ``_print_directory_summary`` 依此打印 "✅ Fixes applied"。
    发现数与应用数在存在 report-only 规则时可以不同 —— 例如自
    ADR-067 起 ``fix-empty-except`` 只报告不应用, 实测 CLI 打印
    "Total fixes: 1 / ✅ Fixes applied" 而磁盘内容**毫无变化**。
    这与 ADR-064/065/066/067 同源: 报告状态与真实状态脱节。

    Args:
        fixer: ASTFixer 实例
        filepath: 文件路径
        dry_run: 是否仅模拟
        verbose: 是否打印详细报告 (默认 False)

    Returns:
        FileFixResult。解析失败或无可修复项时三项均为 0。
    """
    report = fixer.fix_file(filepath, dry_run=dry_run)
    if report is None:
        if verbose:
            print(f"  ⚠️  Cannot parse {filepath}, skipping")
        return FileFixResult(0, 0, 0)
    if report.total_fixes == 0:
        return FileFixResult(0, 0, 0)
    if verbose:
        print(fixer.format_fix_report(report))
    if report.syntax_violation:
        # ADR-070: 自检拦下了会破坏语法的修复。必须在明细里立刻说明,
        # 否则用户只会看到一串 [AUTO] 标记, 以为已经改好。
        print("  ❌ 拒绝写盘: 修复结果无法解析 (ADR-070)")
        print(f"      {report.syntax_error}")
        print("      文件保持原样, 请人工处理后重试")
    return FileFixResult(
        report.total_fixes,
        report.auto_safe_fixes,
        report.applied_fixes,
        bool(report.syntax_violation),
        report.syntax_error,
    )


def _print_directory_summary(
    total_found: int,
    total_auto_safe: int,
    total_applied: int,
    dry_run: bool,
    syntax_violations: int = 0,
) -> None:
    """打印目录级修复汇总 (模块级 helper).

    ADR-068: 同时呈现"发现 / 可自动应用 / 已实际应用"三个数, 并按
    **实际应用数** 而非发现数选择结论行 —— 发现得多但一个都没应用时
    打印 "✅ Fixes applied" 是**假绿灯**。

    ADR-070: 新增 ``syntax_violations``。它是**失败**而非中性信息:
    修复结果无法解析、被拒绝写盘, 是本应自动完成的修复没做成,
    与 ``review-only`` (等人来看) 性质不同, 必须用独立结论行,
    不能混进 review-only 那一句里轻描淡写。

    Args:
        total_found: 发现的可修复项总数
        total_auto_safe: 其中标记为可自动应用的项数
        total_applied: 实际写入磁盘的修复总数 (dry_run 时恒为 0)
        dry_run: 是否仅模拟
        syntax_violations: 因修复结果无法解析而被拒绝写盘的文件数
    """
    print(f"\n{'=' * 60}")
    print(f"  Total fixes found: {total_found} ({total_auto_safe} auto-safe)")
    print(f"  Fixes applied: {total_applied}" + (" (dry run)" if dry_run else ""))
    if syntax_violations:
        print(f"  ❌ {syntax_violations} file(s) rejected: fixes would break syntax (ADR-070)")
        print("      Files left unchanged. Fix the reported syntax error manually.")
    if dry_run:
        if total_found == 0:
            print("  ✅ No fixes needed")
        else:
            print("  ℹ️  Run without --dry-run to apply")
    elif syntax_violations:
        # 必须优先于 applied>0 的分支: 部分文件被拒、部分成功时,
        # 只报成功同样是假绿灯 (总体上确有未完成的修复)。
        print("  ❌ Syntax check failed — see messages above")
    elif total_applied == 0:
        # 发现 > 0 但应用 == 0: 全部是 report-only 规则 (ADR-067),
        # 此时既不能说"已修复", 也不该说"无需修复"。
        if total_found == 0:
            print("  ✅ No fixes needed")
        else:
            print(f"  ℹ️  {total_found} review-only fix(es) reported, none applied automatically")
            print("      (auto_safe=False —— 需人工确认, 见 ADR-067)")
    else:
        print(f"  ✅ Fixes applied: {total_applied}/{total_found}")
    print("=" * 60)


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

    # ADR-065: 同 _run_semantic_check —— 路径不存在时 detect_hallucinations
    # 扫 0 个文件, 报告渲染成 "No hallucination patterns detected", 不可分辨。
    if not path.exists():
        print(f"❌ 路径不存在: {path}")
        return 1

    if path.is_file():
        report = detect_hallucinations_in_file(path)
    else:
        report = detect_hallucinations(path)

    print(format_hallucination_report(report))

    return 0 if report.high_count == 0 else 1
