"""Architect Agent - converts PRDs into technical designs."""

from __future__ import annotations

from .base import BaseAgent, MockLLM
from ..config import AgentConfig
from ..protocol import AgentResponse, Message, MessageRole


class ArchitectAgent(BaseAgent):
    """Architect agent that produces technical designs from PRDs.

    Attributes:
        _role: Fixed to MessageRole.ARCHITECT.
        _llm: The LLM backend (MockLLM for testing).
    """

    _role = MessageRole.ARCHITECT

    def __init__(
        self,
        llm: MockLLM | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(config)
        self._llm = llm or MockLLM()

    def _generate(self, history: list[Message]) -> AgentResponse:
        """Generate a technical design from the latest PRD.

        Args:
            history: Message history (uses the latest message as PRD input).

        Returns:
            AgentResponse with the technical design text.
        """
        prompt = history[-1].content if history else ""
        text = self._llm.generate("Architect", prompt)
        return AgentResponse(
            text=text,
            metadata={"stage": "design"},
        )
