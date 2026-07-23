"""Data models for the language rules engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    """A single code quality issue found during validation."""
    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    column: int = 0
    message: str = ""
    fix_hint: str = ""
    fix_replacement: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
        }
        if self.fix_hint:
            d["fix_hint"] = self.fix_hint
        if self.fix_replacement:
            d["fix_replacement"] = self.fix_replacement
        return d


@dataclass
class ValidationResult:
    """Validation result for a single file."""
    file: str
    language: str
    lines_checked: int = 0
    issues: list[Issue] = field(default_factory=list)
    cached: bool = False

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "language": self.language,
            "lines_checked": self.lines_checked,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
            "cached": self.cached,
        }


@dataclass
class FixResult:
    """Result of applying a fix."""
    file: str
    line: int
    rule_id: str
    original: str
    replacement: str
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "rule_id": self.rule_id,
            "original": self.original,
            "replacement": self.replacement,
            "applied": self.applied,
        }


@dataclass
class HealthScore:
    """Project health score."""
    score: int  # 0-100
    grade: str  # A-F
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    total_files: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "grade": self.grade,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
            "total_files": self.total_files,
        }
