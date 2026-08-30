"""Auto-fix applier for language rules validation.

Provides regex-based auto-fix functionality for code issues.
Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.validators.models import FixResult, Issue


def _read_file_content(filepath: Path) -> tuple[str, bool]:
    """Read file content, return (content, success)."""
    try:
        return filepath.read_text(encoding="utf-8"), True
    except (OSError, UnicodeDecodeError):
        return "", False


def _parse_regex_replacement(replacement: str, original_line: str) -> str | None:
    """Parse and apply sed-style regex replacement. Returns new line or None on error."""
    if not replacement.startswith("s/") or replacement.count("/") < 3:
        return None

    parts = replacement.split("/")
    pattern = parts[1]
    new_text = parts[2]
    flags = parts[3] if len(parts) > 3 else ""
    re_flags = re.IGNORECASE if "i" in flags else 0

    try:
        return re.sub(pattern, new_text, original_line, flags=re_flags)
    except re.error:
        return None


def _apply_literal_replacement(original_line: str, replacement: str, message: str) -> str:
    """Apply literal string replacement."""
    match_text = message.split(":")[-1].strip() if ":" in message else ""
    return original_line.replace(match_text, replacement, 1)


def _apply_fix_to_line(issue: Issue, original_line: str) -> str | None:
    """Apply a single fix to a line. Returns new line or None if no change/error."""
    if not issue.fix_replacement:
        return None

    replacement = issue.fix_replacement

    # Try regex replacement first
    if replacement.startswith("s/"):
        new_line = _parse_regex_replacement(replacement, original_line)
        if new_line is not None:
            return new_line
        return None  # Regex malformed, don't fallback

    # Literal replacement
    return _apply_literal_replacement(original_line, replacement, issue.message)


def _create_fix_result(filepath: Path, issue: Issue, original_line: str, new_line: str) -> FixResult:
    """Create a FixResult from fix details."""
    return FixResult(
        file=str(filepath),
        rule_id=issue.rule_id,
        line=issue.line,
        original=original_line.rstrip(),
        fixed=new_line.rstrip(),
        description=issue.fix_hint or f"Auto-fixed: {issue.rule_id}",
    )


def _process_issues(
    lines: list[str], issues: list[Issue], filepath: Path, dry_run: bool
) -> tuple[list[FixResult], list[str], bool]:
    """Process all issues against lines. Returns (fixes, modified_lines, modified).

    V2.20 P4-59 拆分: 抽 _should_skip_issue 收口守卫 (无 fix / line 越界),
    _apply_line_fix 收口 dry_run 守卫 + line 更新,
    主函数仅 for + 委托.
    """
    fixes: list[FixResult] = []
    modified_lines = lines[:]
    modified = False

    for issue in issues:
        if _should_skip_issue(issue, modified_lines):
            continue

        line_idx = issue.line - 1
        original_line = modified_lines[line_idx]

        new_line = _apply_fix_to_line(issue, original_line)
        if new_line is None or new_line == original_line:
            continue

        fixes.append(_create_fix_result(filepath, issue, original_line, new_line))

        if not dry_run:
            modified_lines[line_idx] = new_line
            modified = True

    return fixes, modified_lines, modified


def _should_skip_issue(issue: Issue, lines: list[str]) -> bool:
    """判断 issue 是否应跳过 (无 fix_replacement 或 line 越界, 模块级 helper).

    Args:
        issue: 待处理 issue
        lines: 当前行列表

    Returns:
        True if 应跳过
    """
    return bool(not issue.fix_replacement or issue.line < 1 or issue.line > len(lines))


def apply_fixes(filepath: Path, issues: list[Any], dry_run: bool = False) -> list[Any]:
    """Apply auto-fixes to a file based on issues with fix_replacement.

    Args:
        filepath: File to fix
        issues: Issues to fix (only those with fix_replacement set)
        dry_run: If True, report what would change without writing

    Returns:
        List of FixResult describing each change
    """
    content, success = _read_file_content(filepath)
    if not success:
        return []

    lines = content.splitlines(keepends=True)
    fixes, modified_lines, modified = _process_issues(lines, issues, filepath, dry_run)

    if modified and not dry_run:
        filepath.write_text("".join(modified_lines), encoding="utf-8")

    return fixes
