"""Result types for correction attempts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto


class CorrectionStatus(Enum):
    """Outcome status of a correction attempt."""

    SUCCESS = auto()
    FAILURE = auto()
    SKIPPED = auto()


@dataclass(frozen=True)
class CorrectionResult:
    """Immutable record of a single correction attempt.

    Attributes:
        status: Whether the attempt succeeded, failed, or was skipped.
        attempt: 1-indexed attempt number.
        strategy: Name of the strategy that produced the fix (or None if skipped).
        message: Human-readable description.
        file_path: Path to the file that was modified.
        original_code: The source code before the fix.
        fixed_code: The source code after the fix (None if no fix applied).
        test_output: Combined stdout+stderr from the test run.
        duration_s: Wall-clock time of this attempt in seconds.
        timestamp: UTC timestamp when the result was created.
    """

    status: CorrectionStatus
    attempt: int
    strategy: str | None = None
    message: str = ""
    file_path: str = ""
    original_code: str = ""
    fixed_code: str | None = None
    test_output: str = ""
    duration_s: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def is_success(self) -> bool:
        """Return True if the correction succeeded."""
        return self.status == CorrectionStatus.SUCCESS

    @property
    def code_changed(self) -> bool:
        """Return True if the fix actually modified the code."""
        return self.fixed_code is not None and self.fixed_code != self.original_code

    def summary(self) -> str:
        """One-line human-readable summary."""
        status_label = self.status.name
        strategy_label = self.strategy or "none"
        return f"[Attempt {self.attempt}] {status_label} (strategy={strategy_label}) {self.message}"


def success_result(
    attempt: int,
    strategy: str,
    file_path: str,
    original_code: str,
    fixed_code: str = "",
    test_output: str = "",
    duration_s: float = 0.0,
) -> CorrectionResult:
    """Convenience constructor for a successful correction."""
    return CorrectionResult(
        status=CorrectionStatus.SUCCESS,
        attempt=attempt,
        strategy=strategy,
        message="Tests passed after fix.",
        file_path=file_path,
        original_code=original_code,
        fixed_code=fixed_code,
        test_output=test_output,
        duration_s=duration_s,
    )


def failure_result(
    attempt: int,
    strategy: str,
    message: str,
    file_path: str = "",
    original_code: str = "",
    fixed_code: str | None = None,
    test_output: str = "",
    duration_s: float = 0.0,
) -> CorrectionResult:
    """Convenience constructor for a failed correction."""
    return CorrectionResult(
        status=CorrectionStatus.FAILURE,
        attempt=attempt,
        strategy=strategy,
        message=message,
        file_path=file_path,
        original_code=original_code,
        fixed_code=fixed_code,
        test_output=test_output,
        duration_s=duration_s,
    )
