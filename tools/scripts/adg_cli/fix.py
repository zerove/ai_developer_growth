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
    """Apply fixes to all code files in a directory (V2.21 P5-21 拆分: 抽 _should_process_file + _compute_applicable_rules)."""
    total_stats = {"fixed": 0, "skipped": 0, "errors": 0, "files": 0}

    for filepath in dirpath.rglob("*"):
        if not filepath.is_file():
            continue
        if not _should_process_file(filepath, dirpath, language):
            continue

        applicable_rules = _compute_applicable_rules(language)
        if not applicable_rules:
            continue

        stats = fix_file(filepath, list(applicable_rules.keys()))
        total_stats["fixed"] += stats["fixed"]
        total_stats["skipped"] += stats["skipped"]
        total_stats["errors"] += stats["errors"]
        if stats["fixed"] > 0:
            total_stats["files"] += 1

    return total_stats


def _should_process_file(filepath: Path, dirpath: Path, language: str | None) -> bool:
    """判断文件是否应处理 (跳过目录/扩展名/语言不匹配, 模块级 helper).

    Args:
        filepath: 文件路径
        dirpath: 扫描根目录
        language: 目标语言 (None 不过滤)

    Returns:
        True 表示应处理
    """
    try:
        rel_parts = filepath.relative_to(dirpath).parts
    except ValueError:
        rel_parts = filepath.parts
    if any(is_skipped_dir(part) for part in rel_parts):
        return False
    if filepath.suffix in SKIP_EXTENSIONS:
        return False
    if language:
        file_lang = _detect_language_from_file(filepath)
        if file_lang and file_lang != language:
            return False
    return True


def _compute_applicable_rules(language: str | None) -> dict[str, Any]:
    """按 language 过滤适用规则 (模块级 helper).

    Args:
        language: 目标语言 (None 不过滤)

    Returns:
        适用规则字典 {rule_id: fix_info}
    """
    applicable: dict[str, Any] = {}
    for rule_id, fix_info in FIX_RULES.items():
        if language is None or fix_info.get("language") in (language, "common"):
            applicable[rule_id] = fix_info
    return applicable
