"""Naming convention checker."""

from __future__ import annotations

import re
from typing import Any

from .models import Issue


def check_naming_conventions(
    lines: list[str],
    rules: dict[str, Any],
    filepath: str,
    language: str,
) -> list[Issue]:
    """Check code against naming conventions."""
    issues: list[Issue] = []
    naming_rules = rules.get("naming", {})

    for convention_name, convention in naming_rules.items():
        if not isinstance(convention, dict):
            continue

        pattern = convention.get("pattern")
        severity = convention.get("severity", "warning")
        message = convention.get("message", f"Naming convention '{convention_name}' violated")
        fix_hint = convention.get("fix_hint", "")

        if not pattern:
            continue

        regex = re.compile(pattern)

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            match = regex.search(line)
            if match:
                issues.append(
                    Issue(
                        rule_id=f"naming-{convention_name}",
                        severity=severity,
                        category="naming",
                        file=filepath,
                        line=line_num,
                        column=match.start(),
                        message=message,
                        fix_hint=fix_hint,
                    )
                )

    return issues
