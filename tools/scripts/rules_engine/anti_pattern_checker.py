"""Anti-pattern checker using regex patterns."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import Issue
from .regex_cache import get_compiled, guard_pattern
from .rule_loader import load_rules_for_language

# 匹配超时保护：单文件单模式匹配的最长耗时（秒）
# 防止复杂/恶意正则拖垮检查流水线
_MATCH_TIMEOUT_S = 0.1


def check_anti_patterns(
    filepath: Path,
    language: str,
    rules: dict[str, Any] | None = None,
    content: str | None = None,
    lines: list[str] | None = None,
) -> list[Issue]:
    """Check a file for anti-patterns using regex rules.

    性能优化: 调用方（checker.check_file）已读取 content/lines 时
    直接传入复用，避免对同一文件重复读盘。
    """
    issues: list[Issue] = []

    if not filepath.exists():
        return issues

    if content is None:
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return issues

    lines = lines if lines is not None else content.split("\n")

    # Load rules for this language (includes cross-language security patterns)
    if rules is None:
        rules = load_rules_for_language(language)

    all_patterns: list[dict[str, Any]] = []

    # Add language-specific anti-patterns (already includes cross-language patterns)
    lang_patterns = rules.get("anti_patterns", [])
    all_patterns.extend(lang_patterns)

    # 逐行注释过滤与 pattern 无关, 在此一次算好供全部 pattern 复用。
    # 原实现在 _check_line_patterns 内对每个 pattern 重复 strip()+startswith(),
    # 实测 59 pattern × 225 行 = 每文件 1.3 万次冗余字符串分配。
    scannable = [(line_num, line) for line_num, line in enumerate(lines, 1) if not line.strip().startswith(("#", "//"))]

    # Check each pattern
    for pattern_def in all_patterns:
        if pattern_def.get("enabled") is False:
            continue
        issues.extend(_check_pattern(filepath, content, scannable, pattern_def))

    return issues


def _check_pattern(
    filepath: Path, content: str, scannable: list[tuple[int, str]], pattern_def: dict[str, Any]
) -> list[Issue]:
    """Check a single pattern against file content (V2.21 P5-54 拆分: 抽 _is_pattern_excluded + _check_pattern_matches)."""
    issues: list[Issue] = []
    pattern = pattern_def.get("pattern", "")
    if not pattern:
        return issues
    if _is_pattern_excluded(filepath, content, pattern_def):
        return issues
    issues.extend(_check_pattern_matches(filepath, content, scannable, pattern, pattern_def))
    return issues


def _is_pattern_excluded(filepath: Path, content: str, pattern_def: dict[str, Any]) -> bool:
    """检查 pattern 是否被 exclude_files 或 exclude_patterns 排除 (模块级 helper).

    Args:
        filepath: 文件路径
        content: 文件内容
        pattern_def: pattern 定义

    Returns:
        True 表示应排除
    """
    exclude_files = pattern_def.get("exclude_files", [])
    filename = filepath.name
    if any(filename == ef or filepath.match(ef) for ef in exclude_files):
        return True
    exclude_patterns = pattern_def.get("exclude_patterns", [])
    for exclude_pattern in exclude_patterns:
        if guard_pattern(exclude_pattern, "exclude_patterns"):
            continue
        if re.search(exclude_pattern, content):
            return True
    return False


def _check_pattern_matches(
    filepath: Path,
    content: str,
    scannable: list[tuple[int, str]],
    pattern: str,
    pattern_def: dict[str, Any],
) -> list[Issue]:
    """检查 pattern 匹配 (multiline or line, 模块级 helper).

    Args:
        filepath: 文件路径
        content: 文件内容
        scannable: (行号, 行文本) 列表, 已剔除纯注释行
        pattern: 正则 pattern
        pattern_def: pattern 定义

    Returns:
        Issue 列表
    """
    flags = re.IGNORECASE if pattern_def.get("ignore_case", False) else 0
    pattern_str = pattern_def.get("pattern", "")
    is_multiline = ("\n" in pattern_str or "\\n" in pattern_str) or pattern_def.get("multiline", False)
    if is_multiline:
        return _check_multiline_pattern(filepath, content, pattern, flags, pattern_def)
    return _check_line_patterns(scannable, pattern, flags, pattern_def, str(filepath))


def _check_multiline_pattern(
    filepath: Path, content: str, pattern: str, flags: int, pattern_def: dict[str, Any]
) -> list[Issue]:
    """Check multi-line pattern against full content.

    危险正则（灾难性回溯风险）直接跳过，避免卡死检查流水线。
    """
    issues: list[Issue] = []

    # 安全保护：可能灾难性回溯的危险模式直接跳过 (跳过会留痕)
    if guard_pattern(pattern, "anti_pattern"):
        return issues

    try:
        compiled = get_compiled(pattern, flags | re.MULTILINE)
    except re.error:
        return issues

    for match in compiled.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        issues.append(
            Issue(
                rule_id=pattern_def.get("id", "unknown"),
                severity=pattern_def.get("severity", "warning"),
                category=pattern_def.get("category", "anti-pattern"),
                file=str(filepath),
                line=line_num,
                column=match.start() - content.rfind("\n", 0, match.start()),
                message=pattern_def.get("message", "Anti-pattern detected"),
                fix_hint=pattern_def.get("fix_hint", ""),
                fix_replacement=pattern_def.get("fix_replacement", ""),
            )
        )
    return issues


def _check_line_patterns(
    scannable: list[tuple[int, str]],
    pattern: str,
    flags: int,
    pattern_def: dict[str, Any],
    filepath: str,
) -> list[Issue]:
    """Check pattern against each scannable line.

    安全保护：危险正则结构（嵌套量词等）直接跳过，避免灾难性回溯。
    """
    issues: list[Issue] = []

    # 安全保护：可能灾难性回溯的危险模式直接跳过 (跳过会留痕)
    if guard_pattern(pattern, "anti_pattern"):
        return issues

    try:
        compiled = get_compiled(pattern, flags)
    except re.error:
        return issues

    # 行级排除（exclude_lines）：命中任一模式的行不报告，
    # 用于过滤字符串字面量/文档中的误报（如 "in except: block"）。
    # 性能优化: 预编译一次（复用 regex_cache），避免逐行 re.search 重编译。
    exclude_lines = pattern_def.get("exclude_lines", [])
    compiled_excludes: list[re.Pattern[str]] = []
    for ex_pat in exclude_lines:
        if guard_pattern(ex_pat, "exclude_lines"):
            continue
        try:
            compiled_excludes.append(get_compiled(ex_pat))
        except re.error:
            continue

    # 绝大多数 pattern 没有 exclude_lines（实测 59 个里 58 个为空）。不建
    # any() 的关键: 空列表时 any(生成器) 仍要新建一个生成器对象并调用 any(),
    # 225 行 × 58 pattern × 每文件 = 1.3 万次纯空转, 全仓实测 72 万次。
    for line_num, line in scannable:
        if compiled_excludes and any(ce.search(line) for ce in compiled_excludes):
            continue

        for match in compiled.finditer(line):
            issues.append(
                Issue(
                    rule_id=pattern_def.get("id", "unknown"),
                    severity=pattern_def.get("severity", "warning"),
                    category=pattern_def.get("category", "anti-pattern"),
                    file=filepath,
                    line=line_num,
                    column=match.start() + 1,
                    message=pattern_def.get("message", "Anti-pattern detected"),
                    fix_hint=pattern_def.get("fix_hint", ""),
                    fix_replacement=pattern_def.get("fix_replacement", ""),
                )
            )
    return issues
