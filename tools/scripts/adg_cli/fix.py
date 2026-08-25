from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.core import FIX_RULES, SKIP_EXTENSIONS, is_skipped_dir
from tools.scripts.adg_cli.detect import _detect_language_from_file


def _apply_fix(content: str, rule_id: str, fix_info: dict[str, Any]) -> tuple[str, bool]:
    """Apply a single fix to content. Returns (new_content, was_modified)."""

    pattern = fix_info.get("pattern")
    replacement = fix_info.get("replacement")

    if not pattern or replacement is None:
        return content, False

    new_content, count = re.subn(pattern, replacement, content)
    return new_content, count > 0


def fix_file(filepath: Path, rule_ids: list[str] | None = None) -> dict[str, Any]:
    """Apply fixes to a file. Returns stats about fixes applied."""

    if not filepath.exists():
        return {"fixed": 0, "skipped": 0, "errors": 1}

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"fixed": 0, "skipped": 0, "errors": 1}

    original_content = content
    fixed_count = 0
    skipped_count = 0

    # Filter rules if specific rule_ids provided
    applicable_rules = FIX_RULES
    if rule_ids:
        applicable_rules = {k: v for k, v in FIX_RULES.items() if k in rule_ids}

    for rule_id, fix_info in applicable_rules.items():
        new_content, was_modified = _apply_fix(content, rule_id, fix_info)
        if was_modified:
            content = new_content
            fixed_count += 1
        else:
            skipped_count += 1

    # Write back if modified
    if content != original_content:
        try:
            filepath.write_text(content, encoding="utf-8")
        except OSError:
            return {"fixed": 0, "skipped": 0, "errors": 1}

    return {"fixed": fixed_count, "skipped": skipped_count, "errors": 0}


def fix_directory(dirpath: Path, language: str | None = None) -> dict[str, Any]:
    """Apply fixes to all code files in a directory."""
    total_stats = {"fixed": 0, "skipped": 0, "errors": 0, "files": 0}

    for filepath in dirpath.rglob("*"):
        if not filepath.is_file():
            continue
        try:
            rel_parts = filepath.relative_to(dirpath).parts
        except ValueError:
            rel_parts = filepath.parts
        if any(is_skipped_dir(part) for part in rel_parts):
            continue
        if filepath.suffix in SKIP_EXTENSIONS:
            continue

        # Filter by language if specified
        if language:
            file_lang = _detect_language_from_file(filepath)
            if file_lang and file_lang != language:
                continue

        # Filter applicable rules by language
        applicable_rules = {}
        for rule_id, fix_info in FIX_RULES.items():
            if language is None or fix_info.get("language") in (language, "common"):
                applicable_rules[rule_id] = fix_info

        if applicable_rules:
            stats = fix_file(filepath, list(applicable_rules.keys()))
            total_stats["fixed"] += stats["fixed"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            if stats["fixed"] > 0:
                total_stats["files"] += 1

    return total_stats
