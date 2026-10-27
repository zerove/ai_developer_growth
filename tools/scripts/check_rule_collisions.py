#!/usr/bin/env python3
"""Detect duplicate rule IDs and undeclared cross-source pattern overlaps."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

try:  # python -m tools.scripts.check_rule_collisions
    from tools.scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # python tools/scripts/check_rule_collisions.py
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

from tools.scripts._common import rules_dir  # noqa: E402


def _load_patterns(path: Path) -> list[dict[str, Any]]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    patterns = data.get("anti_patterns", [])
    return [item for item in patterns if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _sources(root: Path) -> list[tuple[str, Path, list[dict[str, Any]]]]:
    result: list[tuple[str, Path, list[dict[str, Any]]]] = []
    common = root / "common" / "security.yml"
    if common.exists():
        result.append(("common", common, _load_patterns(common)))
    for path in sorted((root / "languages").glob("*/rules.d/anti_patterns.yml")):
        result.append((path.parent.parent.name, path, _load_patterns(path)))
    return result


def _supersedes(rule: dict[str, Any]) -> set[str]:
    value = rule.get("supersedes", [])
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def build_report(root: Path | None = None) -> dict[str, Any]:
    """Build a collision report for the rule YAML tree at ``root``."""
    root = root or rules_dir()
    sources = _sources(root)
    id_sources: dict[str, list[str]] = defaultdict(list)
    common_patterns: dict[str, set[str]] = defaultdict(set)

    for source, _, rules in sources:
        for rule in rules:
            rule_id = rule["id"]
            id_sources[rule_id].append(source)
            pattern = rule.get("pattern")
            if source == "common" and isinstance(pattern, str):
                common_patterns[pattern].add(rule_id)

    overlaps: list[dict[str, str]] = []
    for source, _, rules in sources:
        if source == "common":
            continue
        for rule in rules:
            pattern = rule.get("pattern")
            if not isinstance(pattern, str):
                continue
            declared = _supersedes(rule)
            for common_id in common_patterns.get(pattern, set()):
                if common_id not in declared:
                    overlaps.append(
                        {
                            "source": source,
                            "rule_id": rule["id"],
                            "common_id": common_id,
                        }
                    )

    duplicate_ids = {rule_id: source_names for rule_id, source_names in id_sources.items() if len(source_names) > 1}
    return {
        "root": str(root),
        "rule_count": sum(len(rules) for _, _, rules in sources),
        "duplicate_ids": duplicate_ids,
        "unresolved_pattern_overlaps": overlaps,
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"Rules: {report['rule_count']}")
    duplicate_ids = report["duplicate_ids"]
    overlaps = report["unresolved_pattern_overlaps"]
    if duplicate_ids:
        print("Duplicate rule IDs:")
        for rule_id, sources in sorted(duplicate_ids.items()):
            print(f"  {rule_id}: {', '.join(sources)}")
    if overlaps:
        print("Undeclared cross-source pattern overlaps:")
        for item in overlaps:
            print(f"  {item['source']}:{item['rule_id']} == {item['common_id']}")
    if not duplicate_ids and not overlaps:
        print("OK: no duplicate IDs or unresolved cross-source pattern overlaps")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check rule IDs and cross-language pattern overlaps.")
    parser.add_argument("--root", type=Path, default=None, help="ai-dev-framework directory")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    args = parser.parse_args(argv)

    report = build_report(args.root)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)
    return 1 if report["duplicate_ids"] or report["unresolved_pattern_overlaps"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
