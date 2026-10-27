"""Language rules loader package.

Public API for the legacy rules loading system.

Usage:
    from tools.scripts.rules_loader import load_rules, load_custom_rules
    from tools.scripts.rules_loader import (
        Issue,
        ValidationResult,
        FixResult,
        HealthScore,
    )
    from tools.scripts.rules_loader.cli import add_common_args, output_results
"""

from tools.scripts.rules_engine.models import (  # noqa: F401
    FixResult,
    HealthScore,
    Issue,
    ValidationResult,
)

from .loader import load_custom_rules, load_rules

__all__ = [
    "load_rules",
    "load_custom_rules",
    "Issue",
    "ValidationResult",
    "FixResult",
    "HealthScore",
]
