"""Orchestration modes for multi-agent workflows."""  # noqa: N999

from .adversarial_debate import RedBlueDebateOrchestrator
from .fan_out import FanOutOrchestrator, FanOutResult
from .waterfall import WaterfallOrchestrator, WorkflowResult

__all__ = [
    "FanOutOrchestrator",
    "FanOutResult",
    "WaterfallOrchestrator",
    "WorkflowResult",
    "RedBlueDebateOrchestrator",
]
