"""Data models for language rule validation.

Re-exports from rules_engine/models.py for backward compatibility,
plus additional models specific to validate_language_rules.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Re-export from rules_engine for backward compatibility
from tools.scripts.rules_engine.models import Issue, ValidationResult  # noqa: F401

__all__ = ["Issue", "ValidationResult", "FixResult"]


@dataclass
class FixResult:
    """Result of an auto-fix operation."""

    file: str
    rule_id: str
    line: int
    original: str
    fixed: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "rule_id": self.rule_id,
            "line": self.line,
            "original": self.original,
            "fixed": self.fixed,
            "description": self.description,
        }
