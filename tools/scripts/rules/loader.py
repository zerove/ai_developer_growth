"""Rule loading, merging, and common rules injection.

Provides cached, lazy rule loading with common rules auto-injection.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import rules_dir as _rules_dir  # noqa: I001

# ──────────────────────────────────────────────────────────
# Cached rule loading (#7 lazy loading)
# ──────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=64)
def _load_raw_rules(rule_path_str: str) -> dict[str, Any]:
    """Load raw YAML rules with LRU cache (keyed by path string for hashability)."""
    rule_path = Path(rule_path_str)
    if not rule_path.exists():
        return {}
    with open(rule_path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_rules(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load rules for a language, merging with common rules.

    Results are cached via functools.lru_cache on the raw YAML load.
    Common security rules are automatically merged.
    """
    base_dir = framework_dir or _rules_dir()
    rules_path = base_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    rules = _load_raw_rules(str(rules_path))
    if not rules:
        return _get_embedded_rules(language)

    # Merge common security rules
    common = _load_common_rules(base_dir)
    if common:
        rules = _merge_rules(rules, common)

    return rules


def load_custom_rules(project_dir: Path) -> dict[str, Any]:
    """Load custom rules from .ai-rules/ directory."""
    custom_dir = project_dir / ".ai-rules"
    if not custom_dir.exists():
        return {}

    merged: dict[str, Any] = {}
    for yml_file in sorted(custom_dir.glob("*.yml")):
        try:
            data = _load_raw_rules(str(yml_file))
            if data:
                merged = _merge_rules(merged, data)
        except Exception as e:
            print(f"Warning: Failed to load {yml_file}: {e}", file=sys.stderr)

    return merged


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules (V2.21 P5-63 拆分: 抽 _merge_list_category + _merge_dict_category).

    Rules with matching IDs are overridden (only severity can be overridden
    via severity_override field). New rules are appended.
    """
    result = dict(base)

    for category in [
        "anti_patterns",
        "naming_conventions",
        "complexity",
        "naming",
        "thresholds",
    ]:
        base_items = base.get(category, [])
        custom_items = custom.get(category, [])

        if not custom_items:
            continue

        if isinstance(base_items, list) and isinstance(custom_items, list):
            result[category] = _merge_list_category(base_items, custom_items)
        elif isinstance(base_items, dict) and isinstance(custom_items, dict):
            result[category] = _merge_dict_category(base_items, custom_items)

    return result


def _merge_list_category(base_items: list[Any], custom_items: list[Any]) -> list[Any]:
    """合并 list 类 (按 ID 覆盖 + new 追加, 模块级 helper).

    Args:
        base_items: 基础列表
        custom_items: 自定义列表

    Returns:
        合并后的列表
    """
    base_map: dict[str, dict[str, Any]] = {}
    for item in base_items:
        if isinstance(item, dict) and "id" in item:
            base_map[item["id"]] = item

    for rule in custom_items:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id", "")
        if rule_id in base_map:
            if "severity_override" in rule:
                base_map[rule_id] = {
                    **base_map[rule_id],
                    "severity": rule["severity_override"],
                }
            else:
                base_map[rule_id].update(rule)
        else:
            base_map[rule_id] = rule

    return list(base_map.values())


def _merge_dict_category(base_items: dict[str, Any], custom_items: dict[str, Any]) -> dict[str, Any]:
    """合并 dict 类 (custom 覆盖 base, 模块级 helper).

    Args:
        base_items: 基础 dict
        custom_items: 自定义 dict

    Returns:
        合并后的 dict
    """
    merged = dict(base_items)
    merged.update(custom_items)
    return merged


def _load_common_rules(framework_dir: Path) -> dict[str, Any]:
    """Load common cross-language rules."""
    common_path = framework_dir / "common" / "security.yml"
    if common_path.exists():
        return _load_raw_rules(str(common_path))
    return {}


def _get_embedded_rules(language: str) -> dict[str, Any]:
    """Fallback embedded rules for when YAML files are missing."""
    return {
        "language": language,
        "anti_patterns": [],
        "naming_conventions": [],
        "complexity": [],
    }
