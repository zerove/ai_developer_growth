from __future__ import annotations

import argparse
import json

from ._shared import (
    _RESET,
    _SEVERITY_COLORS,
    load_rules_for_language,
)


def cmd_list_rules(args: argparse.Namespace) -> int:
    """List rules for a specific language."""
    rules = load_rules_for_language(args.lang)
    patterns = rules.get("anti_patterns", [])

    if args.json:
        print(json.dumps(patterns, indent=2, ensure_ascii=False))
        return 0

    print(f"Rules for: {args.lang}")
    print(f"Total: {len(patterns)} anti-patterns\n")

    # Group by severity
    for severity in ("error", "warning", "info"):
        group = [p for p in patterns if p.get("severity") == severity]
        if group:
            color = _SEVERITY_COLORS.get(severity, "")
            print(f"{color}{'=' * 60}")
            print(f"  {severity.upper()} ({len(group)} rules)")
            print(f"{'=' * 60}{_RESET}")
            for p in group:
                print(f"  {p.get('id', 'unknown'):30s}  {p.get('name', '')}")
                if p.get("message"):
                    print(f"  {' ' * 30}  → {p['message']}")
            print()

    return 0
