from __future__ import annotations

import argparse
import sys

from ._shared import (
    Path,
    _collect_test_files,
    _load_rule_from_yaml,
    _print_test_results,
    _test_rule,
)


def _cmd_rule_test(args: argparse.Namespace) -> int:
    """Test a rule against files."""
    rule_file = Path(args.rule_file)
    if not rule_file.exists():
        print(f"Error: Rule file not found: {rule_file}", file=sys.stderr)
        return 1

    # Load rule from YAML
    rule_data = _load_rule_from_yaml(rule_file)

    if not rule_data.get("pattern"):
        print("Error: No pattern found in rule file", file=sys.stderr)
        return 1

    # Get test files
    target = Path(args.path)
    test_files = _collect_test_files(target)

    if not test_files:
        print("No test files found.", file=sys.stderr)
        return 1

    # Test the rule
    results = _test_rule(rule_data, test_files)

    # Output
    _print_test_results(results)

    return 0 if not results["errors"] else 1
