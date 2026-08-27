from __future__ import annotations

import argparse
import sys

from ._cmd_rule_create import _cmd_rule_create  # noqa: F401
from ._cmd_rule_test import _cmd_rule_test  # noqa: F401
from ._cmd_rule_validate import _cmd_rule_validate  # noqa: F401


def cmd_rule(args: argparse.Namespace) -> int:
    """Handle rule authoring commands."""
    rule_cmd = getattr(args, "rule_command", None)

    if rule_cmd == "create":
        return _cmd_rule_create(args)
    elif rule_cmd == "test":
        return _cmd_rule_test(args)
    elif rule_cmd == "validate":
        return _cmd_rule_validate(args)
    else:
        print("Usage: adg rule {create|test|validate}", file=sys.stderr)
        return 1
