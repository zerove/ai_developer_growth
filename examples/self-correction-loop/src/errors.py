"""Exception hierarchy for the self-correction loop."""

from __future__ import annotations


class CorrectionError(Exception):
    """Base exception for all correction-loop errors."""


class TestFailure(CorrectionError):  # noqa: N818
    """Raised when the test suite fails.

    Attributes:
        stdout: Captured standard output.
        stderr: Captured standard error.
        returncode: Process exit code.
    """

    def __init__(
        self,
        message: str,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 1,
    ) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    @property
    def combined_output(self) -> str:
        """Return stdout + stderr as a single string."""
        return f"{self.stdout}\n{self.stderr}".strip()


class FixError(CorrectionError):
    """Raised when applying a code fix fails.

    Attributes:
        file_path: The target file that could not be written.
        reason: Human-readable explanation.
    """

    def __init__(self, message: str, file_path: str = "", reason: str = "") -> None:
        super().__init__(message)
        self.file_path = file_path
        self.reason = reason


class StrategyError(CorrectionError):
    """Raised when a correction strategy fails to produce a fix.

    Attributes:
        strategy_name: Name of the strategy that failed.
    """

    def __init__(self, message: str, strategy_name: str = "") -> None:
        super().__init__(message)
        self.strategy_name = strategy_name
