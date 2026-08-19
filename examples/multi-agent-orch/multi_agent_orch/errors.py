"""Error types for multi-agent orchestration."""

from __future__ import annotations


class AgentError(Exception):
    """Base exception for all agent-related errors.

    Attributes:
        agent_role: The role of the agent that failed, if known.
        cause: The original exception, if wrapping an underlying error.
    """

    def __init__(
        self,
        message: str,
        *,
        agent_role: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.agent_role = agent_role
        self.cause = cause
        super().__init__(message)


class AgentTimeoutError(AgentError):
    """Raised when an agent fails to respond within its timeout window."""


class AgentFailureError(AgentError):
    """Raised when an agent raises an unhandled exception during execution."""


class MaxIterationsError(AgentError):
    """Raised when an iterative workflow exceeds its maximum iteration count.

    Attributes:
        iterations: How many iterations completed before hitting the limit.
    """

    def __init__(self, message: str, *, iterations: int = 0) -> None:
        self.iterations = iterations
        super().__init__(message)


class MalformedResponseError(AgentError):
    """Raised when an agent returns a response that cannot be parsed.

    Attributes:
        raw_output: The unparsable output from the agent.
    """

    def __init__(self, message: str, *, raw_output: str = "") -> None:
        self.raw_output = raw_output
        super().__init__(message)
