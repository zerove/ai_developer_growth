"""Core data models for language rules validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.scripts._common import SeverityCountsMixin


@dataclass
class Issue:
    """A single validation issue."""

    rule_id: str
    severity: str  # error, warning, info
    category: str
    file: str
    line: int
    message: str
    fix_hint: str = ""
    explanation: str = ""  # G2: 为什么这是问题 + 学习引导
    context_role: str = ""  # G1: 检测到的文件角色
    column: int = 0
    fix_replacement: str = ""  # Auto-fix: regex replacement pattern
    related_docs: list[dict[str, str]] = field(default_factory=list)  # Knowledge base links

    def to_dict(self) -> dict[str, Any]:
        d = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }
        if self.fix_replacement:
            d["fix_replacement"] = self.fix_replacement
        if self.related_docs:
            d["related_docs"] = self.related_docs
        return d


@dataclass
class ValidationResult(SeverityCountsMixin):
    """Aggregated validation results for a file."""

    file: str
    language: str
    issues: list[Issue] = field(default_factory=list)
    lines_checked: int = 0

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "language": self.language,
            "passed": self.passed,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "lines_checked": self.lines_checked,
            "issues": [i.to_dict() for i in self.issues],
        }


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


@dataclass
class HealthScore:
    """Project health score (0-100)."""

    score: int
    grade: str
    breakdown: dict[str, float]
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "grade": self.grade,
            "breakdown": self.breakdown,
            "details": self.details,
        }


@dataclass
class CheckResult(SeverityCountsMixin):
    """Result of checking a single file."""

    file: str
    issues: list[Issue] = field(default_factory=list)
    language: str = "unknown"
    skipped: bool = False

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "language": self.language,
            "skipped": self.skipped,
            "passed": self.passed,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
        }


class Severity:
    """Severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @classmethod
    def from_string(cls, value: str) -> str:
        """Normalize severity string."""
        value = value.lower()
        if value in ("error", "critical", "fatal", "2"):
            return cls.ERROR
        if value in ("warning", "warn", "1"):
            return cls.WARNING
        return cls.INFO
