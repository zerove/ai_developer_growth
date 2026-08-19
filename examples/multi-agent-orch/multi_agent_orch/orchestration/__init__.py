"""Orchestration modes for multi-agent workflows."""  # noqa: N999

from .fan_out import FanOutOrchestrator, FanOutResult
from .waterfall import WaterfallOrchestrator, WorkflowResult
from .adversarial_debate import RedBlueDebateOrchestrator

__all__ = [
    "FanOutOrchestrator",
    "FanOutResult",
    "WaterfallOrchestrator",
    "WorkflowResult",
    "RedBlueDebateOrchestrator",
]
