#!/usr/bin/env python3
"""Detect duplicate rule IDs, invalid IDs, and undeclared cross-source pattern overlaps."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

try:  # python -m tools.scripts.check_rule_collisions
    from tools.scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # python tools/scripts/check_rule_collisions.py
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

from tools.scripts._common import rules_dir  # noqa: E402


def _load_patterns(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (valid_rules, invalid_id_entries).

    valid_rules: dict rules with non-empty string id and no whitespace in id.
    invalid_id_entries: entries with missing/invalid/malformed ids for reporting.
    """
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    patterns = data.get("anti_patterns", [])
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for item in patterns:
        if not isinstance(item, dict):
            invalid.append({"reason": "not-a-dict"})
            continue
        rid = item.get("id")
        if not isinstance(rid, str) or not rid.strip():
            invalid.append({"reason": "missing-or-empty-id", "id": rid})
            continue
        if re.search(r"\s", rid):
            invalid.append({"reason": "whitespace-in-id", "id": rid})
            continue
        valid.append(item)
    return valid, invalid


def _sources(root: Path) -> list[tuple[str, Path, list[dict[str, Any]], list[dict[str, Any]]]]:
    result: list[tuple[str, Path, list[dict[str, Any]], list[dict[str, Any]]]] = []
    common = root / "common" / "security.yml"
    if common.exists():
        valid, invalid = _load_patterns(common)
        result.append(("common", common, valid, invalid))
    for path in sorted((root / "languages").glob("*/rules.d/anti_patterns.yml")):
        valid, invalid = _load_patterns(path)
        result.append((path.parent.parent.name, path, valid, invalid))
    return result


def _supersedes(rule: dict[str, Any]) -> set[str]:
    value = rule.get("supersedes", [])
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def _expected_prefix(source: str) -> str:
    """Expected rule ID prefix for a framework rule source."""
    if source == "common":
        return "common-"
    from tools.scripts._common import rule_id_prefix

    return f"{rule_id_prefix(source)}-"


def _collect_overlaps(
    sources: list[tuple[str, Path, list[dict[str, Any]], list[dict[str, Any]]]],
    common_patterns: dict[str, set[str]],
) -> list[dict[str, str]]:
    overlaps: list[dict[str, str]] = []
    for source, _, rules, _ in sources:
        if source == "common":
            continue
        for rule in rules:
            pattern = rule.get("pattern")
            if not isinstance(pattern, str):
                continue
            declared = _supersedes(rule)
            for common_id in common_patterns.get(pattern, set()):
                if common_id not in declared:
                    overlaps.append({"source": source, "rule_id": rule["id"], "common_id": common_id})
    return overlaps


def build_report(root: Path | None = None, *, strict: bool = False) -> dict[str, Any]:
    """Build a collision report for the rule YAML tree at ``root``."""
    root = root or rules_dir()
    sources = _sources(root)
    id_sources: dict[str, list[str]] = defaultdict(list)
    common_patterns: dict[str, set[str]] = defaultdict(set)
    invalid_ids: list[dict[str, Any]] = []
    prefix_violations: list[dict[str, Any]] = []

    for source, path, rules, invalid in sources:
        for entry in invalid:
            invalid_ids.append({"source": source, "file": str(path), **entry})
        expected = _expected_prefix(source)
        for rule in rules:
            rule_id = rule["id"]
            id_sources[rule_id].append(source)
            if strict and not rule_id.startswith(expected):
                prefix_violations.append(
                    {"source": source, "file": str(path), "rule_id": rule_id, "expected_prefix": expected}
                )
            pattern = rule.get("pattern")
            if source == "common" and isinstance(pattern, str):
                common_patterns[pattern].add(rule_id)

    duplicate_ids = {rid: srcs for rid, srcs in id_sources.items() if len(srcs) > 1}
    return {
        "root": str(root),
        "rule_count": sum(len(rules) for _, _, rules, _ in sources),
        "duplicate_ids": duplicate_ids,
        "invalid_ids": invalid_ids,
        "prefix_violations": prefix_violations,
        "unresolved_pattern_overlaps": _collect_overlaps(sources, common_patterns),
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"Rules: {report['rule_count']}")
    duplicate_ids = report["duplicate_ids"]
    invalid_ids = report.get("invalid_ids", [])
    prefix_violations = report.get("prefix_violations", [])
    overlaps = report["unresolved_pattern_overlaps"]
    if duplicate_ids:
        print("Duplicate rule IDs:")
        for rule_id, sources in sorted(duplicate_ids.items()):
            print(f"  {rule_id}: {', '.join(sources)}")
    if invalid_ids:
        print("Invalid rule IDs:")
        for item in invalid_ids:
            rid = item.get("id")
            print(f"  {item['source']}: {item.get('reason')} ({rid!r})")
    if prefix_violations:
        print("Rule ID prefix violations:")
        for item in prefix_violations:
            print(f"  {item['source']}:{item['rule_id']} (expected prefix: {item['expected_prefix']})")
    if overlaps:
        print("Undeclared cross-source pattern overlaps:")
        for item in overlaps:
            print(f"  {item['source']}:{item['rule_id']} == {item['common_id']}")
    if not duplicate_ids and not invalid_ids and not prefix_violations and not overlaps:
        print("OK: no duplicate IDs, invalid IDs, prefix violations, or unresolved cross-source pattern overlaps")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check rule IDs, invalid IDs, prefix consistency, and cross-language pattern overlaps."
    )
    parser.add_argument("--root", type=Path, default=None, help="ai-dev-framework directory")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="enforce rule ID prefix consistency for framework sources",
    )
    args = parser.parse_args(argv)

    report = build_report(args.root, strict=args.strict)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)
    has_error = bool(
        report["duplicate_ids"]
        or report.get("invalid_ids")
        or report.get("prefix_violations")
        or report["unresolved_pattern_overlaps"]
    )
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
