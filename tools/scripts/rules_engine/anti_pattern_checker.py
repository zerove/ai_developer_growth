"""Anti-pattern checker using regex patterns."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import Issue
from .regex_cache import get_compiled, get_dangerous
from .rule_loader import load_rules_for_language

# 匹配超时保护：单文件单模式匹配的最长耗时（秒）
# 防止复杂/恶意正则拖垮检查流水线
_MATCH_TIMEOUT_S = 0.1


def check_anti_patterns(filepath: Path, language: str, rules: dict[str, Any] | None = None) -> list[Issue]:
    """Check a file for anti-patterns using regex rules."""
    issues: list[Issue] = []

    if not filepath.exists():
        return issues

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return issues

    lines = content.split("\n")

    # Load rules for this language (includes cross-language security patterns)
    if rules is None:
        rules = load_rules_for_language(language)

    all_patterns: list[dict[str, Any]] = []

    # Add language-specific anti-patterns (already includes cross-language patterns)
    lang_patterns = rules.get("anti_patterns", [])
    all_patterns.extend(lang_patterns)

    # Check each pattern
    for pattern_def in all_patterns:
        if pattern_def.get("enabled") is False:
            continue
        issues.extend(_check_pattern(filepath, content, lines, pattern_def))

    return issues


def _check_pattern(filepath: Path, content: str, lines: list[str], pattern_def: dict[str, Any]) -> list[Issue]:
    """Check a single pattern against file content."""
    issues: list[Issue] = []
    pattern = pattern_def.get("pattern", "")
    if not pattern:
        return issues

    # Check exclude_files - skip rule if filename matches any excluded file
    exclude_files = pattern_def.get("exclude_files", [])
    filename = filepath.name
    if any(filename == ef or filepath.match(ef) for ef in exclude_files):
        return issues

    # Check exclude patterns first - if any exclude pattern matches, skip this pattern
    exclude_patterns = pattern_def.get("exclude_patterns", [])
    for exclude_pattern in exclude_patterns:
        if re.search(exclude_pattern, content):
            return issues  # Skip this pattern entirely if exclude matches

    flags = re.IGNORECASE if pattern_def.get("ignore_case", False) else 0
    # Check if pattern is multi-line (contains \n or \\n)
    pattern_str = pattern_def.get("pattern", "")
    is_multiline = ("\n" in pattern_str or "\\n" in pattern_str) or pattern_def.get("multiline", False)

    if is_multiline:
        issues.extend(_check_multiline_pattern(filepath, content, pattern, flags, pattern_def))
    else:
        issues.extend(_check_line_patterns(lines, pattern, flags, pattern_def, str(filepath)))

    return issues


def _check_multiline_pattern(
    filepath: Path, content: str, pattern: str, flags: int, pattern_def: dict[str, Any]
) -> list[Issue]:
    """Check multi-line pattern against full content.

    危险正则（灾难性回溯风险）直接跳过，避免卡死检查流水线。
    """
    issues: list[Issue] = []

    # 安全保护：可能灾难性回溯的危险模式直接跳过
    if get_dangerous(pattern):
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
    lines: list[str],
    pattern: str,
    flags: int,
    pattern_def: dict[str, Any],
    filepath: str,
) -> list[Issue]:
    """Check pattern against each line.

    安全保护：危险正则结构（嵌套量词等）直接跳过，避免灾难性回溯。
    """
    issues: list[Issue] = []

    # 安全保护：可能灾难性回溯的危险模式直接跳过
    if get_dangerous(pattern):
        return issues

    try:
        compiled = get_compiled(pattern, flags)
    except re.error:
        return issues

    for line_num, line in enumerate(lines, 1):
        # Skip comments for most patterns
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # 行级排除（exclude_lines）：命中任一模式的行不报告，
        # 用于过滤字符串字面量/文档中的误报（如 "in except: block"）
        exclude_lines = pattern_def.get("exclude_lines", [])
        if any(re.search(ex_pat, line) for ex_pat in exclude_lines):
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
