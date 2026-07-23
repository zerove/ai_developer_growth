"""Language rules engine package.

Public API for the rules validation system.

Usage:
    from rules import load_rules, load_custom_rules
    from rules.models import Issue, ValidationResult, FixResult, HealthScore
    from rules.cli import add_common_args, output_results
"""

from rules.loader import load_custom_rules, load_rules
from rules.models import FixResult, HealthScore, Issue, ValidationResult

__all__ = [
    "load_rules",
    "load_custom_rules",
    "Issue",
    "ValidationResult",
    "FixResult",
    "HealthScore",
]
