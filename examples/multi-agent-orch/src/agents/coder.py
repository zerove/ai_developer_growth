"""Coder Agent - produces code from designs or review feedback."""

from __future__ import annotations

from src.agents.base import BaseAgent, MockLLM
from src.config import AgentConfig
from src.protocol import AgentResponse, Message, MessageRole


class CoderAgent(BaseAgent):
    """Coder agent that writes code from designs or fix requests.

    Attributes:
        _role: Fixed to MessageRole.CODER.
        _llm: The LLM backend (MockLLM for testing).
    """

    _role = MessageRole.CODER

    def __init__(
        self,
        llm: MockLLM | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(config)
        self._llm = llm or MockLLM()

    def _generate(self, history: list[Message]) -> AgentResponse:
        """Generate code from design or review feedback.

        On the first iteration, receives the design doc. On subsequent
        iterations, receives "FIX: <reviewer feedback>".

        Args:
            history: Message history (latest message is design or fix request).

        Returns:
            AgentResponse with the generated code.
        """
        prompt = history[-1].content if history else ""
        text = self._llm.generate("Coder", prompt)
        return AgentResponse(
            text=text,
            metadata={"stage": "code"},
        )
