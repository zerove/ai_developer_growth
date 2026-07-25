#!/usr/bin/env python3
"""Rule test framework (#5): validate YAML rule regex patterns against test cases.

Each YAML rule can include test_cases:
    anti_patterns:
      - id: py-bare-except
        pattern: 'except\\s*:'
        test_cases:
          - code: 'except:'
            should_match: true
          - code: 'except Exception:'
            should_match: false

Usage:
    python tools/scripts/validate_rule_tests.py --all
    python tools/scripts/validate_rule_tests.py --lang python
"""

from __future__ import annotations

import re
import sys
from typing import Any

import yaml

from tools.scripts._common import handle_error
from tools.scripts._common import rules_dir as _rules_dir


def _load_rules_with_tests(lang: str) -> list[dict[str, Any]]:
    """Load rules that have test_cases for a language."""
    rules: list[dict[str, Any]] = []
    rules_dir = _rules_dir() / "languages" / lang / "rules.d"
    if not rules_dir.exists():
        return rules

    for yml in sorted(rules_dir.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        for category in ["anti_patterns", "naming_conventions", "complexity", "thresholds"]:
            for rule in data.get(category, []):
                if isinstance(rule, dict) and rule.get("test_cases"):
                    rules.append(
                        {
                            "file": str(yml),
                            "category": category,
                            "rule": rule,
                        }
                    )
    return rules


def validate_rule_tests(lang: str) -> tuple[int, int, list[str]]:
    """Validate all rule test cases for a language.

    Returns (passed, failed, error_messages).
    """
    passed = 0
    failed = 0
    errors: list[str] = []

    rules = _load_rules_with_tests(lang)
    if not rules:
        errors.append(f"No rules with test_cases found for '{lang}'")
        return 0, 0, errors

    for entry in rules:
        rule = entry["rule"]
        rule_id = rule["id"]
        pattern = rule.get("pattern", "")
        category = entry["category"]

        if not pattern:
            errors.append(f"[{category}] {rule_id}: no pattern to test")
            continue

        try:
            compiled = re.compile(pattern)
        except re.error as e:
            errors.append(f"[{category}] {rule_id}: invalid regex: {e}")
            failed += 1
            continue

        for i, tc in enumerate(rule["test_cases"]):
            code = tc["code"]
            should_match = tc.get("should_match", True)
            did_match = bool(compiled.search(code))

            if did_match == should_match:
                passed += 1
            else:
                failed += 1
                expected = "match" if should_match else "no match"
                actual = "matched" if did_match else "no match"
                errors.append(f"[{category}] {rule_id} case {i + 1}: expected {expected}, got {actual} on: {code!r}")

    return passed, failed, errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate YAML rule regex test cases")
    parser.add_argument("--lang", type=str, help="Language to test")
    parser.add_argument("--all", action="store_true", help="Test all languages")
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

        total_passed = 0
        total_failed = 0
        all_errors: list[str] = []
        lang_results: list[dict[str, Any]] = []

        for lang in languages:
            passed, failed, errors = validate_rule_tests(lang)
            total_passed += passed
            total_failed += failed
            all_errors.extend(errors)

            lang_results.append(
                {
                    "language": lang,
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                }
            )

            if not args.json_output:
                if failed:
                    print(f"  ✗ {lang}: {passed} passed, {failed} FAILED")
                else:
                    print(f"  ✓ {lang}: {passed} passed")

        if args.json_output:
            import json

            print(
                json.dumps(
                    {
                        "total_passed": total_passed,
                        "total_failed": total_failed,
                        "languages": lang_results,
                    },
                    indent=2,
                )
            )
        else:
            print(f"\n{'=' * 40}")
            print(f"Total: {total_passed} passed, {total_failed} failed")

            if all_errors and args.verbose:
                print("\nFailures:")
                for err in all_errors:
                    print(f"  ✗ {err}")

        return 1 if total_failed > 0 else 0
    except Exception as e:
        handle_error(e, script="validate_rule_tests")
        return 1


if __name__ == "__main__":
    sys.exit(main())
