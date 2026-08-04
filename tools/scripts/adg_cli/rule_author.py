from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_RULE_TEMPLATE = """# {id}
# Language: {language}
# Category: {category}
# Severity: {severity}

- id: {id}
  severity: {severity}
  category: {category}
  pattern: "{pattern}"
  message: "{message}"
  fix_hint: "{fix_hint}"
"""


def _create_rule_interactive() -> dict[str, Any]:
    """Interactively create a new rule."""
    print("=== ADG Rule Creator ===\n")

    rule_id = input("Rule ID (e.g., py-custom-rule): ").strip()
    if not rule_id:
        return {}

    language = input("Language (python/javascript/rust/go/typescript): ").strip()
    if not language:
        return {}

    category = input("Category (security/code_quality/performance/maintainability): ").strip()
    if not category:
        category = "code_quality"

    severity = input("Severity (error/warning/info): ").strip()
    if not severity:
        severity = "warning"

    pattern = input("Regex pattern to match: ").strip()
    if not pattern:
        return {}

    message = input("Issue message: ").strip()
    fix_hint = input("Fix hint (optional): ").strip()

    return {
        "id": rule_id,
        "language": language,
        "category": category,
        "severity": severity,
        "pattern": pattern,
        "message": message,
        "fix_hint": fix_hint,
    }


def _validate_rule(rule: dict[str, Any]) -> list[str]:
    """Validate a rule definition. Returns list of errors."""
    errors = []

    required_fields = ["id", "severity", "category", "pattern", "message"]
    for field in required_fields:
        if not rule.get(field):
            errors.append(f"Missing required field: {field}")

    if rule.get("severity") not in ("error", "warning", "info"):
        errors.append(f"Invalid severity: {rule.get('severity')}")

    if rule.get("category") not in ("security", "code_quality", "performance", "maintainability"):
        errors.append(f"Invalid category: {rule.get('category')}")

    # Test regex pattern
    if rule.get("pattern"):
        try:
            re.compile(rule["pattern"])
        except re.error as e:
            errors.append(f"Invalid regex pattern: {e}")

    return errors


def _test_rule(rule: dict[str, Any], test_files: list[Path]) -> dict[str, Any]:
    """Test a rule against test files."""
    results = {
        "rule_id": rule.get("id", "unknown"),
        "files_tested": len(test_files),
        "matches": [],
        "errors": [],
    }

    try:
        pattern = re.compile(rule["pattern"])
    except re.error as e:
        results["errors"].append(f"Invalid pattern: {e}")
        return results

    for filepath in test_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    results["matches"].append(
                        {
                            "file": str(filepath),
                            "line": line_num,
                            "column": 1,
                            "match": line.strip()[:100],
                        }
                    )
        except (OSError, UnicodeDecodeError) as e:
            results["errors"].append(f"Error reading {filepath}: {e}")

    return results
