from __future__ import annotations

import argparse
import sys

from ._shared import (
    Path,
    _expand_rule_set,
    _load_rules_from_file,
    _validate_rule,
)


def _cmd_rule_validate(args: argparse.Namespace) -> int:
    """Validate a rule file.

    支持两种格式：
    - 单规则 dict（含 id/severity/category/pattern/message）
    - 规则集合（{"anti_patterns": [...]} 或顶层 list），逐条校验
    """
    rule_file = Path(args.rule_file)
    if not rule_file.exists():
        print(f"Error: Rule file not found: {rule_file}", file=sys.stderr)
        return 1

    rules = _expand_rule_set(_load_rules_from_file(rule_file))

    if not rules:
        print(f"\n❌ Validation failed for: {rule_file}")
        print("  - No rules found in file")
        return 1

    all_errors: list[str] = []
    for label, rule in rules:
        for e in _validate_rule(rule):
            all_errors.append(f"{label}: {e}")

    if all_errors:
        print(f"\n❌ Validation failed for: {rule_file} ({len(rules)} rules)")
        for e in all_errors[:30]:
            print(f"  - {e}")
        if len(all_errors) > 30:
            print(f"  ... and {len(all_errors) - 30} more")
        return 1

    print(f"\n✅ Validation passed for: {rule_file} ({len(rules)} rules)")
    return 0
