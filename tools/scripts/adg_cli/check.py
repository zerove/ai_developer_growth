from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.core import (
    SKIP_DIRS_ALL,
    SKIP_EXTENSIONS,
    Issue,
    _make_issue,
    _severity_rank,
)
from tools.scripts.adg_cli.detect import _detect_language_from_file, detect_language
from tools.scripts.adg_cli.git import (
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
)


def _check_ast_semantic(
    filepath: Path,
    lines: list[str],
    severity_filter: str | None,
) -> list[Issue]:
    """AST 语义检查: bare-raise 的 except 块判定 (正则无法表达)。"""
    if filepath.suffix != ".py":
        return []

    from tools.scripts.rules_engine.ast_semantic import check_python_bare_raise

    result: list[Issue] = []
    for ast_issue in check_python_bare_raise(str(filepath), lines):
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

    for pattern_def in rules.get("anti_patterns", []):
        # 显式禁用的规则跳过 (如已迁移到 AST 实现的 py-bare-raise)
        if pattern_def.get("enabled") is False:
            continue
        severity = pattern_def.get("severity", "warning")
        if severity_filter and _severity_rank(severity) > _severity_rank(severity_filter):
            continue

        issues.extend(_check_pattern(filepath, content, lines, pattern_def))

    issues.extend(_check_ast_semantic(filepath, lines, severity_filter))

    return issues


def _check_pattern(filepath: Path, content: str, lines: list[str], pattern_def: dict[str, Any]) -> list[Issue]:
    """Check a single pattern against file content."""
    issues: list[Issue] = []
    pattern = pattern_def.get("pattern", "")
    if not pattern:
        return issues

    # Check exclude files (glob patterns against path or basename)
    for exclude in pattern_def.get("exclude_files", []):
        if _match_pattern(filepath, exclude):
            return []

    # Check exclude patterns
    for exclude in pattern_def.get("exclude_patterns", []):
        if re.search(exclude, content):
            return []

    flags = re.IGNORECASE if pattern_def.get("ignore_case", False) else 0
    is_multiline = ("\n" in pattern or "\\n" in pattern) or pattern_def.get("multiline", False)

    if is_multiline:
        try:
            for match in re.finditer(pattern, content, flags | re.MULTILINE):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(_make_issue(filepath, line_num, 0, pattern_def))
        except re.error:
            pass
    else:
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            try:
                for match in re.finditer(pattern, line, flags):
                    issues.append(_make_issue(filepath, line_num, match.start() + 1, pattern_def))
            except re.error:
                continue

    return issues


def check_directory(
    dirpath: Path,
    rules: dict[str, Any],
    severity_filter: str | None = None,
    jobs: int = 1,
) -> list[Issue]:
    """Check all code files in a directory.

    Args:
        dirpath: Directory to check
        rules: Rules to apply
        severity_filter: Filter by severity level
        jobs: Number of parallel jobs (1 = sequential)
    """
    # Collect files first
    files_to_check: list[Path] = []
    for filepath in dirpath.rglob("*"):
        if not filepath.is_file():
            continue
        try:
            rel_parts = filepath.relative_to(dirpath).parts
        except ValueError:
            rel_parts = filepath.parts
        if any(part in SKIP_DIRS_ALL for part in rel_parts):
            continue
        if filepath.suffix in SKIP_EXTENSIONS:
            continue
        lang = _detect_language_from_file(filepath)
        if lang:
            files_to_check.append(filepath)

    # Check files (parallel or sequential)
    if jobs > 1 and len(files_to_check) > 1:
        return _check_files_parallel(files_to_check, rules, severity_filter, jobs)
    else:
        all_issues: list[Issue] = []
        for filepath in files_to_check:
            all_issues.extend(check_file(filepath, rules, severity_filter))
        return all_issues


def _check_files_parallel(
    files: list[Path], rules: dict[str, Any], severity_filter: str | None, jobs: int
) -> list[Issue]:
    """Check files in parallel using ProcessPoolExecutor."""
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
            try:
                issues = future.result()
                all_issues.extend(issues)
            except Exception as e:
                # Log error but continue processing
                filepath = future_to_file[future]
                print(f"Warning: Error checking {filepath}: {e}", file=sys.stderr)

    return all_issues


def _collect_check_files(
    target: Path, args: argparse.Namespace, project_config: dict[str, Any]
) -> tuple[list[Path], dict[str, Any]]:
    """Collect files to check and language detection info. Returns (files, detected)."""
    files: list[Path] = []
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
        for fp in target.rglob("*"):
            try:
                rel_parts = fp.relative_to(target).parts
            except ValueError:
                rel_parts = fp.parts
            if fp.is_file() and not any(part in SKIP_DIRS_ALL for part in rel_parts):
                if fp.suffix not in SKIP_EXTENSIONS:
                    if any(_match_pattern(fp, pat) for pat in skip_patterns):
                        continue
                    # Also match against path relative to scan target (skip_patterns
                    # are written as repo-relative globs like "tests/*")
                    try:
                        rel = fp.relative_to(target)
                    except ValueError:
                        rel = fp
                    if any(_match_pattern(rel, pat) for pat in skip_patterns):
                        continue
                    if _detect_language_from_file(fp):
                        files.append(fp)
        detected = detect_language(target)

    return files, detected


def _match_pattern(filepath: Path, pattern: str) -> bool:
    """Check if filepath matches a glob pattern."""
    import fnmatch

    return fnmatch.fnmatch(str(filepath), pattern) or fnmatch.fnmatch(filepath.name, pattern)
