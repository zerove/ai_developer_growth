"""validators package - Modular language rule validation system.

Submodules:
    models: Data models (Issue, ValidationResult, FixResult, HealthScore).
    pipeline: Core validation logic (detect language, load rules, validate).
    cli: CLI entry point and argument parsing.
    health: Health score calculation.
"""

from tools.scripts.validators.health import HealthScore, calculate_health_score
from tools.scripts.validators.models import FixResult, Issue, ValidationResult
from tools.scripts.validators.pipeline import (
    EXTENSION_MAP,
    check_anti_patterns,
    detect_language_from_file,
    load_custom_rules,
    load_rules,
    validate_directory,
    validate_file,
)

__all__ = [
    "EXTENSION_MAP",
    "FixResult",
    "HealthScore",
    "Issue",
    "ValidationResult",
    "calculate_health_score",
    "check_anti_patterns",
    "detect_language_from_file",
    "load_custom_rules",
    "load_rules",
    "validate_directory",
    "validate_file",
]
