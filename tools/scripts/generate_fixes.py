#!/usr/bin/env python3
"""AI-assisted fix generator (#8): generate fix_replacement for rules without one.

Uses heuristic-based generation when no LLM API key is available.
Optionally uses OpenAI/Claude API if OPENAI_API_KEY or ANTHROPIC_API_KEY is set.

Usage:
    python tools/scripts/generate_fixes.py --all --dry-run
    python tools/scripts/generate_fixes.py --lang python -o fixes.json
    python tools/scripts/generate_fixes.py --lang typescript --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import yaml

from tools.scripts._common import handle_error
from tools.scripts._common import rules_dir as _rules_dir
from tools.scripts.fix_heuristics import (
    HEURISTIC_FIXES,  # noqa: F401 - re-export for tests
    heuristic_fix,  # noqa: F401 - re-export for tests
)

# Re-export for backward compatibility
__all__ = ["heuristic_fix", "HEURISTIC_FIXES"]


def _load_rules_without_fix(lang: str) -> list[dict[str, Any]]:
    """Load rules that don't have fix_replacement."""
    rules: list[dict[str, Any]] = []
    lang_dir = _rules_dir() / "languages" / lang / "rules.d"
    if not lang_dir.exists():
        return rules

    for yml in sorted(lang_dir.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        for category in ["anti_patterns", "naming_conventions", "complexity"]:
            for rule in data.get(category, []):
                if not rule.get("fix_replacement"):
                    rules.append(
                        {
                            "file": str(yml),
                            "category": category,
                            "lang": lang,
                            "rule": rule,
                        }
                    )
    return rules


def generate_fixes(languages: list[str], dry_run: bool = False) -> list[dict[str, Any]]:
    """Generate fixes for rules without fix_replacement across languages."""
    results = []
    for lang in languages:
        entries = _load_rules_without_fix(lang)
        for entry in entries:
            rule = entry["rule"]
            fix_info = heuristic_fix(rule)
            results.append(
                {
                    "lang": lang,
                    "file": entry["file"],
                    "category": entry["category"],
                    "id": rule["id"],
                    "pattern": rule.get("pattern", ""),
                    "message": rule.get("message", ""),
                    **fix_info,
                }
            )
    return results


def apply_fixes_to_yaml(fixes: list[dict[str, Any]], dry_run: bool = True) -> int:
    """Apply generated fixes back to YAML files. Returns number of fixes applied."""
    if dry_run:
        return len(fixes)

    applied = 0
    # Group by file
    by_file: dict[str, list[dict[str, Any]]] = {}
    for fix in fixes:
        if fix["fix_replacement"]:
            by_file.setdefault(fix["file"], []).append(fix)

    for filepath, file_fixes in by_file.items():
        with open(filepath) as f:
            data = yaml.safe_load(f)
        if not data:
            continue

        for fix in file_fixes:
            for category in ["anti_patterns", "naming_conventions", "complexity"]:
                for rule in data.get(category, []):
                    if rule["id"] == fix["id"] and not rule.get("fix_replacement"):
                        rule["fix_replacement"] = fix["fix_replacement"]
                        applied += 1

        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fix_replacement for rules")
    parser.add_argument("--lang", type=str, help="Process specific language")
    parser.add_argument("--all", action="store_true", help="Process all languages")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--apply", action="store_true", help="Apply fixes to YAML files")
    parser.add_argument("-o", "--output", type=str, help="Output JSON file")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Detailed output")
    args = parser.parse_args()

    try:
        if not args.all and not args.lang:
            parser.error("Must specify --lang or --all")

        # Discover languages
        if args.all:
            langs_dir = _rules_dir() / "languages"
            languages = sorted(d.name for d in langs_dir.iterdir() if d.is_dir() and (d / "rules.d").exists())
        else:
            languages = [args.lang]

        fixes = generate_fixes(languages, dry_run=args.dry_run)
        total = len(fixes)
        with_fix = sum(1 for f in fixes if f["fix_replacement"])

        if args.json_output:
            print(json.dumps(fixes, indent=2))
        else:
            print(f"Generated fixes for {with_fix}/{total} rules")
            if args.verbose:
                for fix in fixes:
                    print(f"  [{fix['lang']}] {fix['id']}: {fix.get('fix_replacement', '') or '(no fix)'}")

        if args.output:
            with open(args.output, "w") as f:
                json.dump(fixes, f, indent=2)
            print(f"Output written to {args.output}")

        if args.apply:
            applied = apply_fixes_to_yaml(fixes, dry_run=False)
            print(f"Applied {applied} fixes to YAML files")
        elif args.dry_run:
            for fix in fixes[:10]:
                print(f"  [{fix['lang']}] {fix['id']}: {fix['fix_replacement'] or '(no fix)'}")
            if len(fixes) > 10:
                print(f"  ... and {len(fixes) - 10} more")

        return 0
    except Exception as e:
        handle_error(e, script="generate_fixes")
        return 1  # unreachable


if __name__ == "__main__":
    sys.exit(main())
