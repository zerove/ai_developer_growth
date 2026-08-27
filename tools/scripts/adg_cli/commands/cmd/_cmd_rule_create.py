from __future__ import annotations

import argparse
import sys

from ._shared import (
    _RULE_TEMPLATE,
    Path,
    _create_rule_interactive,
    _validate_rule,
)


def _cmd_rule_create(args: argparse.Namespace) -> int:
    """Create a new rule interactively."""
    rule = _create_rule_interactive()

    if not rule:
        print("Rule creation cancelled.", file=sys.stderr)
        return 1

    # Validate
    errors = _validate_rule(rule)
    if errors:
        print("Rule validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Output
    output_path = getattr(args, "output", None)
    if output_path:
        yaml_content = _RULE_TEMPLATE.format(**rule)
        Path(output_path).write_text(yaml_content)
        print(f"Rule saved to: {output_path}")
    else:
        print("\nGenerated rule:")
        print(_RULE_TEMPLATE.format(**rule))

    return 0
