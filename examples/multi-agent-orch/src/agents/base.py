"""Base agent ABC and mock LLM for testing."""

from __future__ import annotations

from abc import ABC, abstractmethod

from config import AgentConfig
from errors import AgentFailureError
from protocol import AgentResponse, Message, MessageRole


class BaseAgent(ABC):
    """Abstract base for all agents. Implements the Agent protocol.

    Subclasses must implement _generate(). This class handles config,
    error wrapping, and the run() interface.

    Attributes:
        _role: The MessageRole this agent represents.
        _config: Configuration for this agent instance.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self._config = config or AgentConfig(role=self._role.value)

    @property
    def role(self) -> MessageRole:
        return self._role

    @property
    def config(self) -> AgentConfig:
        return self._config

    def run(self, history: list[Message]) -> AgentResponse:
        """Execute the agent, wrapping errors in AgentFailureError.

        Args:
            history: Full conversation history.

        Returns:
            AgentResponse from _generate().

        Raises:
            AgentFailureError: If _generate() raises any exception.
        """
        try:
            return self._generate(history)
        except AgentFailureError:
            raise
        except Exception as exc:
            raise AgentFailureError(
                f"Agent {self._role.value} failed: {exc}",
                agent_role=self._role.value,
                cause=exc,
            ) from exc

    @abstractmethod
    def _generate(self, history: list[Message]) -> AgentResponse:
        """Generate a response from the message history.

        Args:
            history: Full conversation history.

        Returns:
            AgentResponse with the agent's output.
        """
        ...


class MockLLM:
    """Simulates LLM responses for testing without external dependencies.

    Provides deterministic, role-specific responses. No time.sleep() or
    network calls. Useful for unit tests and the demo entry point.
    """

    def generate(self, role: str, prompt: str) -> str:
        """Generate a mock response based on role and input.

        Args:
            role: Agent role name (e.g. "PM", "Coder").
            prompt: The input prompt/history text.

        Returns:
            Simulated LLM response string.
        """
        if role == "PM":
            return (
                f"[PRD] Project: {prompt}\n"
                "- Goal: Create a functional tool.\n"
                "- Requirements: Input amount, select currency,\n"
                "  output converted value.\n"
                "- Success Criteria: Accuracy and simplicity."
            )
        if role == "Architect":
            return (
                f"[Design] Based on PRD: {prompt}\n"
                "- Component: CurrencyConverter Class\n"
                "- Method: convert(amount, from_curr, to_curr)\n"
                "- API: JSON interface { 'amount': float, 'from': str, 'to': str }"
                " -> { 'result': float }"
            )
        if role == "Coder":
            if "FIX" in prompt:
                return (
                    "def convert(amount, from_curr, to_curr):\n"
                    "    # Fixed: Added error handling\n"
                    "    try:\n"
                    "        rate = 1.1\n"
                    "        return amount * rate\n"
                    "    except Exception as e:\n"
                    "        return str(e)"
                )
            return (
                "def convert(amount, from_curr, to_curr):\n"
                "    rate = 1.1\n"
                "    return amount * rate"
            )
        if role == "Reviewer":
            if "error handling" in prompt:
                return "PASS: Code looks good now."
            return "FAIL: Missing error handling for invalid inputs."
        return "I don't know how to handle this."
