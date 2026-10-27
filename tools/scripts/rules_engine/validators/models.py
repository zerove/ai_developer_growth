"""Data models for language rule validation.

Re-exports from rules_engine/models.py for backward compatibility,
plus additional models specific to validate_language_rules.py.
"""

from __future__ import annotations

# Re-export from rules_engine for backward compatibility
from tools.scripts.rules_engine.models import (  # noqa: F401
    FixResult,
    Issue,
    ValidationResult,
)

__all__ = [
    "Issue",
    "ValidationResult",
    "FixResult",
    "ValidationError",
    "RuleLoadError",
    "ValidationExecutionError",
]


class ValidationError(Exception):
    """Base exception for rule validation errors."""


class RuleLoadError(ValidationError):
    """Raised when loading rules fails."""


class ValidationExecutionError(ValidationError):
    """Raised when running validation pipeline fails."""
