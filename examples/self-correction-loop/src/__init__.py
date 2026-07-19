"""Self-correction loop: AI-powered code repair via test feedback."""

from src.errors import CorrectionError, FixError, StrategyError, TestFailure
from src.results import CorrectionResult
from src.runner import CorrectionLoop

__all__ = [
    "CorrectionError",
    "CorrectionLoop",
    "CorrectionResult",
    "FixError",
    "StrategyError",
    "TestFailure",
]
