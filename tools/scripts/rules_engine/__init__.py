"""Rules Engine - Pluggable code quality checking engine.

This package provides a modular rules engine for code quality checks,
supporting multiple languages and pluggable checkers.
"""

from .checker import check_directory, check_file
from .models import CheckResult, Issue, Severity
from .rule_loader import load_rules_for_language

__all__ = [
    "CheckResult",
    "Issue",
    "Severity",
    "check_directory",
    "check_file",
    "load_rules_for_language",
]

__version__ = "1.0.0"
