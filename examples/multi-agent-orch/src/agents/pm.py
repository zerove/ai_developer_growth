"""PM Agent - converts user requests into structured PRDs."""

from __future__ import annotations

from src.agents.base import BaseAgent, MockLLM
from src.config import AgentConfig
from src.protocol import AgentResponse, Message, MessageRole


class PMAgent(BaseAgent):
    """Product Manager agent that produces PRDs from user requests.

    Attributes:
        _role: Fixed to MessageRole.PM.
        _llm: The LLM backend (MockLLM for testing).
    """

    _role = MessageRole.PM

    def __init__(
        self,
        llm: MockLLM | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(config)
        self._llm = llm or MockLLM()

    def _generate(self, history: list[Message]) -> AgentResponse:
        """Generate a PRD from the user's initial request.

        Extracts the user message and asks the LLM to produce a structured
        PRD document.

        Args:
            history: Message history (uses the latest user message).

        Returns:
            AgentResponse with the PRD text.
        """
        prompt = history[-1].content if history else ""
        text = self._llm.generate("PM", prompt)
        return AgentResponse(
            text=text,
            metadata={"stage": "prd"},
        )
