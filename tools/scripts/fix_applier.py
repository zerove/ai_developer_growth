"""Auto-fix applier for language rules validation.

Provides regex-based auto-fix functionality for code issues.
Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def apply_fixes(filepath: Path, issues: list[Any], dry_run: bool = False) -> list[Any]:
    """Apply auto-fixes to a file based on issues with fix_replacement.

    Args:
        filepath: File to fix
        issues: Issues to fix (only those with fix_replacement set)
        dry_run: If True, report what would change without writing

    Returns:
        List of FixResult describing each change
    """
    # Lazy import to avoid circular dependencies
    from .validate_language_rules import FixResult

    fixes: list[FixResult] = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return fixes

    lines = content.splitlines(keepends=True)
    modified = False

    for issue in issues:
        if not issue.fix_replacement or issue.line < 1 or issue.line > len(lines):
            continue

        line_idx = issue.line - 1
        original_line = lines[line_idx]

        # Try regex replacement on the line
        try:
            # fix_replacement format: "s/pattern/replacement/flags" or literal string
            replacement = issue.fix_replacement
            if replacement.startswith("s/") and replacement.count("/") >= 3:
                # sed-style: s/pattern/replacement/flags
                parts = replacement.split("/")
                pattern = parts[1]
                new_text = parts[2]
                flags = parts[3] if len(parts) > 3 else ""
                re_flags = re.IGNORECASE if "i" in flags else 0
                new_line = re.sub(pattern, new_text, original_line, flags=re_flags)
            else:
                # Literal replacement of matched text
                new_line = original_line.replace(
                    issue.message.split(":")[-1].strip() if ":" in issue.message else "",
                    replacement,
                    1,
                )

            if new_line != original_line:
                fixes.append(
                    FixResult(
                        file=str(filepath),
                        rule_id=issue.rule_id,
                        line=issue.line,
                        original=original_line.rstrip(),
                        fixed=new_line.rstrip(),
                        description=issue.fix_hint or f"Auto-fixed: {issue.rule_id}",
                    )
                )
                if not dry_run:
                    lines[line_idx] = new_line
                    modified = True
        except re.error:
            continue

    if modified and not dry_run:
        filepath.write_text("".join(lines), encoding="utf-8")

    return fixes
