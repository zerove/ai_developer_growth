from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from tools.scripts._common import walk_files
from tools.scripts.adg_cli.core import (
    SKIP_EXTENSIONS,
    Issue,
    _make_issue,
    _severity_rank,
    is_skipped_dir,
)
from tools.scripts.adg_cli.detect import _detect_language_from_file, detect_language
from tools.scripts.adg_cli.git import (
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
)
from tools.scripts.app_config import get_setting
from tools.scripts.rules_engine.regex_cache import guard_pattern


def _check_ast_semantic(
    filepath: Path,
    lines: list[str],
    severity_filter: str | None,
) -> list[Issue]:
    """AST 语义检查: bare-raise 的 except 块判定 (正则无法表达)。"""
    if filepath.suffix != ".py":
        return []

    from tools.scripts.rules_engine.ast_semantic import run_ast_semantic_rules

    result: list[Issue] = []
    for ast_issue in run_ast_semantic_rules(str(filepath), lines, "python"):
        if severity_filter and _severity_rank(ast_issue.severity) > _severity_rank(severity_filter):
            continue
        result.append(
            Issue(
                rule_id=ast_issue.rule_id,
                severity=ast_issue.severity,
                category=ast_issue.category,
                file=str(filepath),
                line=ast_issue.line,
                column=ast_issue.column,
                message=ast_issue.message,
                fix_hint=ast_issue.fix_hint,
            )
        )
    return result


def _check_python_complexity(
    filepath: Path,
    lines: list[str],
    severity_filter: str | None,
    max_cc: int,
) -> list[Issue]:
    """圈复杂度门禁: cc >= max_cc 的函数报 error (adg check --complexity)."""
    if filepath.suffix != ".py":
        return []

    import ast

    from tools.scripts.complexity_analyzer import calc_cyclomatic_complexity

    result: list[Issue] = []
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        complexity = calc_cyclomatic_complexity(node)
        if complexity < max_cc:
            continue
        result.append(
            Issue(
                rule_id="py-ast-complexity",
                severity="error",
                category="readability",
                file=str(filepath),
                line=node.lineno,
                column=getattr(node, "col_offset", 0) + 1,
                message=f"Function '{node.name}' has cyclomatic complexity {complexity} (max {max_cc})",
                fix_hint="Refactor into smaller functions",
            )
        )
    return result


def check_file(filepath: Path, rules: dict[str, Any], severity_filter: str | None = None) -> list[Issue]:
    """Check a single file against rules."""
    issues: list[Issue] = []

    if not filepath.exists() or filepath.stat().st_size == 0:
        return issues

    # Skip generated/minified files
    if filepath.suffix in SKIP_EXTENSIONS or filepath.name.endswith(".min.js"):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return issues

    lines = content.split("\n")

    issues.extend(_check_anti_patterns(filepath, content, lines, rules, severity_filter))
    issues.extend(_check_ast_semantic(filepath, lines, severity_filter))

    return issues


def _check_anti_patterns(
    filepath: Path,
    content: str,
    lines: list[str],
    rules: dict[str, Any],
    severity_filter: str | None,
) -> list[Issue]:
    """对文件运行所有 anti-pattern 检查 (模块级 helper)."""
    issues: list[Issue] = []
    for pattern_def in rules.get("anti_patterns", []):
        if pattern_def.get("enabled") is False:
            continue
        severity = pattern_def.get("severity", "warning")
        if severity_filter and _severity_rank(severity) > _severity_rank(severity_filter):
            continue
        issues.extend(_check_pattern(filepath, content, lines, pattern_def))
    return issues


def _check_pattern(filepath: Path, content: str, lines: list[str], pattern_def: dict[str, Any]) -> list[Issue]:
    """Check a single pattern against file content (V2.21 P5-22 拆分: 抽 _is_pattern_excluded + _scan_multiline + _scan_line_by_line)."""
    issues: list[Issue] = []
    pattern = pattern_def.get("pattern", "")
    if not pattern:
        return issues
    if _is_pattern_excluded(filepath, content, pattern_def):
        return []

    flags = re.IGNORECASE if pattern_def.get("ignore_case", False) else 0
    is_multiline = ("\n" in pattern or "\\n" in pattern) or pattern_def.get("multiline", False)

    if is_multiline:
        _scan_multiline(filepath, content, pattern, flags, pattern_def, issues)
    else:
        _scan_line_by_line(filepath, lines, pattern, flags, pattern_def, issues)
    return issues


def _is_pattern_excluded(filepath: Path, content: str, pattern_def: dict[str, Any]) -> bool:
    """检查 pattern 是否被 exclude_files/exclude_patterns 排除 (模块级 helper).

    Args:
        filepath: 文件路径
        content: 文件内容
        pattern_def: pattern 定义

    Returns:
        True 表示已排除 (跳过匹配)
    """
    for exclude in pattern_def.get("exclude_files", []):
        if _match_pattern(filepath, exclude):
            return True
    for exclude in pattern_def.get("exclude_patterns", []):
        if guard_pattern(exclude, "exclude_patterns"):
            continue
        if re.search(exclude, content):
            return True
    return False


def _scan_multiline(
    filepath: Path,
    content: str,
    pattern: str,
    flags: int,
    pattern_def: dict[str, Any],
    issues: list[Issue],
) -> None:
    """多行模式扫描 (模块级 helper, 追加 issue).

    Args:
        filepath: 文件路径
        content: 完整内容
        pattern: 正则 pattern
        flags: re flags
        pattern_def: pattern 定义
        issues: 追加目标 list
    """
    try:
        if guard_pattern(pattern, "main/multiline"):
            return
        for match in re.finditer(pattern, content, flags | re.MULTILINE):
            line_num = content[: match.start()].count("\n") + 1
            issues.append(_make_issue(filepath, line_num, 0, pattern_def))
    except re.error:
        pass


def _scan_line_by_line(
    filepath: Path,
    lines: list[str],
    pattern: str,
    flags: int,
    pattern_def: dict[str, Any],
    issues: list[Issue],
) -> None:
    """逐行扫描 (跳过注释 + exclude_lines, 模块级 helper).

    Args:
        filepath: 文件路径
        lines: 源码行列表
        pattern: 正则 pattern
        flags: re flags
        pattern_def: pattern 定义
        issues: 追加目标 list
    """
    exclude_lines = pattern_def.get("exclude_lines", [])
    guarded_excludes = [p for p in exclude_lines if not guard_pattern(p, "exclude_lines")]
    if guard_pattern(pattern, "main/line"):
        return
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        if any(re.search(ex_pat, line) for ex_pat in guarded_excludes):
            continue
        try:
            for match in re.finditer(pattern, line, flags):
                issues.append(_make_issue(filepath, line_num, match.start() + 1, pattern_def))
        except re.error:
            continue


def check_directory(
    dirpath: Path,
    rules: dict[str, Any],
    severity_filter: str | None = None,
    jobs: int | None = None,
) -> list[Issue]:
    """Check all code files in a directory (V2.21 P5-35 拆分: 抽 _collect_files + _run_checks).

    Args:
        dirpath: Directory to check
        rules: Rules to apply
        severity_filter: Filter by severity level
        jobs: Number of parallel jobs (None/<=0 = use configured default from [tool.adg] jobs, default 4)
    """
    files_to_check = _collect_files(dirpath)
    effective_jobs = jobs if jobs and jobs > 0 else int(str(get_setting("jobs", default=4) or 4))
    return _run_checks(files_to_check, rules, severity_filter, effective_jobs)


def _collect_files(dirpath: Path) -> list[Path]:
    """递归收集目录中所有可检查的语言文件 (模块级 helper).

    跳过 is_skipped_dir / SKIP_EXTENSIONS, 只保留 _detect_language_from_file 命中的文件.

    Args:
        dirpath: 扫描根目录

    Returns:
        文件路径列表
    """
    files_to_check: list[Path] = []
    for filepath in walk_files(dirpath, skip_dir=is_skipped_dir):
        if not filepath.is_file():
            continue
        if is_skipped_dir(filepath.name):
            continue
        if filepath.suffix in SKIP_EXTENSIONS:
            continue
        if _detect_language_from_file(filepath):
            files_to_check.append(filepath)
    return files_to_check


def _run_checks(files: list[Path], rules: dict[str, Any], severity_filter: str | None, jobs: int) -> list[Issue]:
    """运行检查 (parallel or sequential, 模块级 helper).

    Args:
        files: 待检查文件列表
        rules: 规则
        severity_filter: 严重度过滤
        jobs: 并行数 (1 = sequential)

    Returns:
        全部 issue 列表。**单个文件检查失败也算 issue**（`check-error`），
        以保证并行与串行对同一输入给出相同的退出码（ADR-078）。
    """
    if jobs > 1 and len(files) > 1:
        return _check_files_parallel(files, rules, severity_filter, jobs)
    all_issues: list[Issue] = []
    for filepath in files:
        try:
            all_issues.extend(check_file(filepath, rules, severity_filter))
        except Exception as exc:  # noqa: BLE001 - 崩溃必须留痕, 不得静默跳过
            all_issues.append(_make_check_error_issue(filepath, exc))
    return all_issues


def _make_check_error_issue(filepath: Path, exc: BaseException) -> Issue:
    """把“文件检查失败”本身变成一条 error 级 Issue (ADR-078).

    不这样做的话：worker 崩溃的文件会被静默剔除，调用方拿到的 issue
    列表与“该文件干净”**无法区分**，于是 `adg check` 对一个实际未检查的
    文件返回退出码 0（fail-open）。把崩溃升格为 error 后，退出码必然
    非零，且崩溃文件在输出里可见。
    """
    return Issue(
        rule_id="check-error",
        severity="error",
        category="infrastructure",
        file=str(filepath),
        line=1,
        column=1,
        message=f"检查失败，该文件未被检查: {type(exc).__name__}: {exc}",
        fix_hint="检查该文件是否可读、是否被其他进程占用，或用 --jobs 1 重试",
    )


def _check_files_parallel(
    files: list[Path], rules: dict[str, Any], severity_filter: str | None, jobs: int
) -> list[Issue]:
    """Check files in parallel using ProcessPoolExecutor.

    worker 抛异常时**不静默剔除**该文件，而是生成一条 `check-error`
    error 级 Issue（ADR-078），确保调用方能区分“干净”与“没检查到”。
    """
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    if not files:
        return []

    all_issues: list[Issue] = []

    # Limit jobs to CPU count or file count
    max_workers = min(jobs, len(files), os.cpu_count() or 4)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all files for checking
        future_to_file = {executor.submit(check_file, filepath, rules, severity_filter): filepath for filepath in files}

        # Collect results as they complete
        for future in as_completed(future_to_file):
            filepath = future_to_file[future]
            try:
                issues = future.result()
                all_issues.extend(issues)
            except Exception as exc:  # noqa: BLE001 - 崩溃必须留痕, 不得静默剔除
                # ADR-078: 旧实现只 print 警告, 使崩溃文件从结果中消失,
                # 导致该文件被漏检且退出码仍为 0。改为升格为 error Issue。
                all_issues.append(_make_check_error_issue(filepath, exc))
                print(
                    f"Warning: Error checking {filepath}: {exc}",
                    file=sys.stderr,
                )

    return all_issues


def _is_test_file(fp: Path) -> bool:
    """Heuristically determine whether this is a test file (consistent with the pre_tool hook exemption criteria)."""
    parts = fp.parts
    name = fp.name
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.go")
        or name.endswith("Test.java")
        or name.endswith("Tests.cs")
        or name == "conftest.py"
    )


def _build_exclude_patterns(args: argparse.Namespace) -> list[str]:
    """从 CLI 参数构造排除 glob 列表.

    V2.17 拆分: 从 _collect_check_files (C=31) 抽出.
    """
    patterns: list[str] = list(getattr(args, "exclude", []) or [])
    if getattr(args, "exclude_tests", False):
        patterns += ["tests/*", "**/tests/*", "test_*", "*_test.py", "conftest.py"]
    return patterns


def _collect_directory_files(target: Path, skip_patterns: list[str]) -> list[Path]:
    """递归扫描目录 (V2.21 P5-34 拆分: 抽 _passes_skip_filters + _is_checkable_language_file).

    应用 skip_patterns + SKIP_EXTENSIONS 过滤.
    V2.17 拆分: 从 _collect_check_files (C=31) 抽出.
    """
    files: list[Path] = []
    for fp in walk_files(target, skip_dir=is_skipped_dir):
        if not fp.is_file():
            continue
        if not _passes_skip_filters(fp, target, skip_patterns):
            continue
        if _is_checkable_language_file(fp):
            files.append(fp)
    return files


def _passes_skip_filters(fp: Path, target: Path, skip_patterns: list[str]) -> bool:
    """检查文件是否通过所有 skip 过滤 (模块级 helper).

    检查 4 层过滤:
    1. is_skipped_dir (skip 目录)
    2. SKIP_EXTENSIONS (跳过扩展名)
    3. fp 自身 match skip_patterns
    4. rel path match skip_patterns

    Args:
        fp: 文件路径
        target: 扫描根目录
        skip_patterns: glob 模式列表

    Returns:
        True 表示应保留
    """
    try:
        rel_parts = fp.relative_to(target).parts
    except ValueError:
        rel_parts = fp.parts
    if any(is_skipped_dir(part) for part in rel_parts):
        return False
    if fp.suffix in SKIP_EXTENSIONS:
        return False
    if any(_match_pattern(fp, pat) for pat in skip_patterns):
        return False
    try:
        rel = fp.relative_to(target)
    except ValueError:
        rel = fp
    if any(_match_pattern(rel, pat) for pat in skip_patterns):
        return False
    return True


def _is_checkable_language_file(fp: Path) -> bool:
    """判断文件是否在 ADG 支持的语言 (模块级 helper).

    Args:
        fp: 文件路径

    Returns:
        是否可检查的语言文件
    """
    return bool(_detect_language_from_file(fp))


def _apply_exclude_filters(files: list[Path], args: argparse.Namespace, target: Path) -> list[Path]:
    """应用 --exclude / --exclude-tests 过滤.

    V2.17 拆分: 从 _collect_check_files (C=31) 抽出.
    """
    exclude_patterns = _build_exclude_patterns(args)
    if not exclude_patterns:
        return files
    filtered: list[Path] = []
    for fp in files:
        try:
            rel = fp.relative_to(target)
        except ValueError:
            rel = fp
        if any(_match_pattern(fp, pat) or _match_pattern(rel, pat) for pat in exclude_patterns):
            continue
        if getattr(args, "exclude_tests", False) and _is_test_file(fp):
            continue
        filtered.append(fp)
    removed = len(files) - len(filtered)
    if removed:
        print(f"Excluded {removed} file(s) by pattern.", file=sys.stderr)
    return filtered


def _collect_check_files(
    target: Path, args: argparse.Namespace, project_config: dict[str, Any]
) -> tuple[list[Path], dict[str, Any]]:
    """Collect files to check and language detection info. Returns (files, detected).

    V2.17 拆分: 从 C=31 / 74 行主函数拆出 3 个 helper.
    主函数仅负责根据 mode 分发, 行数 < 40.
    """
    since = getattr(args, "since", None)
    staged = getattr(args, "staged", False)
    unstaged = getattr(args, "unstaged", False)

    if since:
        files = _get_git_changed_files(since, cwd=target.parent)
        if not files:
            print("No changed files found.", file=sys.stderr)
        detected = detect_language(target)
    elif staged:
        files = _get_staged_files(cwd=target.parent)
        if not files:
            print("No staged files found.", file=sys.stderr)
        detected = detect_language(target)
    elif unstaged:
        files = _get_unstaged_files(cwd=target.parent)
        if not files:
            print("No unstaged changes found.", file=sys.stderr)
        detected = detect_language(target)
    elif target.is_file():
        files = [target]
        detected = detect_language(target.parent)
    else:
        skip_patterns = project_config.get("skip_patterns", [])
        files = _collect_directory_files(target, skip_patterns)
        detected = detect_language(target)

    files = _apply_exclude_filters(files, args, target)
    return files, detected


def _match_pattern(filepath: Path, pattern: str) -> bool:
    """Check if filepath matches a glob pattern."""
    import fnmatch

    return fnmatch.fnmatch(str(filepath), pattern) or fnmatch.fnmatch(filepath.name, pattern)
