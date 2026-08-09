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


def _calculate_penalties(results: list[Any]) -> dict[str, float]:
    """Calculate penalty values from validation results."""
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)
    total_files = len(results)
    failed_files = sum(1 for r in results if not r.passed)
    clean_files = total_files - failed_files

    return {
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "total_info": total_info,
        "total_files": total_files,
        "failed_files": failed_files,
        "clean_files": clean_files,
        "error_penalty": total_errors * -5.0,
        "warning_penalty": total_warnings * -2.0,
        "info_penalty": total_info * -0.5,
        "failure_penalty": failed_files * -3.0,
    }


def _calculate_score(penalties: dict[str, float]) -> tuple[int, float]:
    """Calculate final score and clean bonus."""
    score = 100.0
    score += penalties["error_penalty"]
    score += penalties["warning_penalty"]
    score += penalties["info_penalty"]
    score += penalties["failure_penalty"]

    # Bonus for clean files (max +10)
    bonus = min(penalties["clean_files"] * 2, 10)
    score += bonus

    # Clamp to 0-100
    score = max(0, min(100, round(score)))

    return score, bonus


def _calculate_grade(score: int) -> str:
    """Calculate letter grade from score."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    return "F"


def _generate_details(penalties: dict[str, float], bonus: float) -> list[str]:
    """Generate human-readable detail strings."""
    details: list[str] = []
    if penalties["total_errors"] > 0:
        details.append(f"{penalties['total_errors']} errors found ({penalties['error_penalty']:.0f} points)")
    if penalties["total_warnings"] > 0:
        details.append(f"{penalties['total_warnings']} warnings found ({penalties['warning_penalty']:.0f} points)")
    if penalties["failed_files"] > 0:
        details.append(f"{penalties['failed_files']} files failed ({penalties['failure_penalty']:.0f} points)")
    if penalties["clean_files"] > 0:
        details.append(f"{penalties['clean_files']} files clean (+{bonus:.0f} points)")
    if not details:
        details.append("All files clean")
    return details


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
    penalties = _calculate_penalties(results)
    score, bonus = _calculate_score(penalties)
    grade = _calculate_grade(score)

    breakdown = {
        "error_penalty": penalties["error_penalty"],
        "warning_penalty": penalties["warning_penalty"],
        "info_penalty": penalties["info_penalty"],
        "failure_penalty": penalties["failure_penalty"],
        "clean_bonus": bonus,
    }

    details = _generate_details(penalties, bonus)

    return HealthScore(score=score, grade=grade, breakdown=breakdown, details=details)
