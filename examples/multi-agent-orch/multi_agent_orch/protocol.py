"""Core protocol and message types for multi-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class MessageRole(Enum):
    """Roles that produce messages in the workflow."""

    USER = "user"
    PM = "PM"
    ARCHITECT = "Architect"
    CODER = "Coder"
    REVIEWER = "Reviewer"


@dataclass(frozen=True)
class Message:
    """A single message in the agent conversation history.

    Attributes:
        role: Who produced this message.
        content: The text content of the message.
        metadata: Optional key-value pairs attached to the message.
    """

    role: MessageRole
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Structured output from an agent.

    Attributes:
        text: The primary response text.
        passed: Whether this response signals approval (used by Reviewer).
        metadata: Additional structured data (e.g. review comments, code files).
    """

    text: str
    passed: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    """Protocol that all agents must implement.

    An agent receives the full message history and produces a structured response.
    This is the core contract - any object matching this interface can participate
    in any orchestration mode.
    """

    @property
    def role(self) -> MessageRole:
        """The role this agent plays in the workflow."""
        ...

    def run(self, history: list[Message]) -> AgentResponse:
        """Process message history and produce a response.

        Args:
            history: Complete conversation history up to this point.

        Returns:
            AgentResponse with the agent's output.

        Raises:
            AgentError: If the agent fails to produce a valid response.
        """
        ...
