"""Health score calculation for language rule validation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def calculate_health_score(results: list[Any]) -> HealthScore:
    """Calculate project health score (0-100) from validation results.

    Scoring:
    - Base: 100
    - Each error: -5 points
    - Each warning: -2 points
    - Each info: -0.5 points
    - Bonus: +2 per clean file (max +10)
    - Penalty for file-level failures: -3 per failed file
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)
    total_files = len(results)
    failed_files = sum(1 for r in results if not r.passed)
    clean_files = total_files - failed_files

    # Base score
    score = 100.0

    # Penalties
    score -= total_errors * 5.0
    score -= total_warnings * 2.0
    score -= total_info * 0.5
    score -= failed_files * 3.0

    # Bonus for clean files
    bonus = min(clean_files * 2, 10)
    score += bonus

    # Clamp
    score = max(0, min(100, round(score)))

    # Grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    # Breakdown
    breakdown = {
        "error_penalty": total_errors * -5.0,
        "warning_penalty": total_warnings * -2.0,
        "info_penalty": total_info * -0.5,
        "failure_penalty": failed_files * -3.0,
        "clean_bonus": bonus,
    }

    # Details
    details: list[str] = []
    if total_errors > 0:
        details.append(f"{total_errors} errors found (-{total_errors * 5} points)")
    if total_warnings > 0:
        details.append(f"{total_warnings} warnings found (-{total_warnings * 2} points)")
    if failed_files > 0:
        details.append(f"{failed_files} files failed (-{failed_files * 3} points)")
    if clean_files > 0:
        details.append(f"{clean_files} files clean (+{bonus} points)")
    if not details:
        details.append("All files clean")

    return HealthScore(score=score, grade=grade, breakdown=breakdown, details=details)
