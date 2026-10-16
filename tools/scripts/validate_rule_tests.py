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

import argparse

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import re
import sys
from typing import Any

import yaml

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from tools.scripts._common import discover_languages, handle_error  # noqa: E402
from tools.scripts._common import rules_dir as _rules_dir  # noqa: E402
from tools.scripts.rules_engine.regex_cache import guard_pattern  # noqa: E402


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
        for category in [
            "anti_patterns",
            "naming_conventions",
            "complexity",
            "thresholds",
        ]:
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

        # pattern 来自 rules_dir 下的规则 yml, 而 code 来自同一份 yml 的
        # test_cases —— 两者在 PR 场景都由外部贡献者控制。实测 `(x|xx)+$` 配
        # 34 字符的 code 需 ~9s, 40 字符即挂死本工具。
        if guard_pattern(pattern, f"validate_rule_tests/{rule_id}"):
            errors.append(f"[{category}] {rule_id}: pattern 疑似灾难性回溯, 已跳过其用例")
            failed += 1
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


def _run_language_validation(lang: str) -> tuple[int, int, list[str]]:
    """Run validation for a single language."""
    return validate_rule_tests(lang)


def _print_results(lang: str, passed: int, failed: int, json_output: bool) -> None:
    """Print results for a single language."""
    if not json_output:
        if failed:
            print(f"  ✗ {lang}: {passed} passed, {failed} FAILED")
        else:
            print(f"  ✓ {lang}: {passed} passed")


def _print_summary(
    total_passed: int,
    total_failed: int,
    all_errors: list[str],
    json_output: bool,
    verbose: bool,
    lang_results: list[dict[str, Any]],
) -> int:
    """Print summary and return exit code."""
    if json_output:
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

        if all_errors and verbose:
            print("\nFailures:")
            for err in all_errors:
                print(f"  ✗ {err}")

    return 1 if total_failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate YAML rule regex test cases")
    parser.add_argument("--lang", type=str, help="Language to test")
    parser.add_argument("--all", action="store_true", help="Test all languages")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Detailed output")
    args = parser.parse_args()

    try:
        if not args.all and not args.lang:
            parser.error("Must specify --lang or --all")

        languages = discover_languages(args)

        total_passed = 0
        total_failed = 0
        all_errors: list[str] = []
        lang_results: list[dict[str, Any]] = []

        for lang in languages:
            passed, failed, errors = _run_language_validation(lang)
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

            _print_results(lang, passed, failed, args.json_output)

        return _print_summary(
            total_passed,
            total_failed,
            all_errors,
            args.json_output,
            args.verbose,
            lang_results,
        )
    except Exception as e:
        handle_error(e, script="validate_rule_tests")
        return 1


if __name__ == "__main__":
    sys.exit(main())
