"""Reviewer Agent - evaluates code and produces PASS/FAIL verdicts."""

from __future__ import annotations

from agents.base import BaseAgent, MockLLM
from config import AgentConfig
from protocol import AgentResponse, Message, MessageRole


class ReviewerAgent(BaseAgent):
    """Reviewer agent that evaluates code and decides PASS or FAIL.

    The response text is parsed for "PASS" or "FAIL" keywords to set
    the AgentResponse.passed flag.

    Attributes:
        _role: Fixed to MessageRole.REVIEWER.
        _llm: The LLM backend (MockLLM for testing).
    """

    _role = MessageRole.REVIEWER

    def __init__(
        self,
        llm: MockLLM | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(config)
        self._llm = llm or MockLLM()

    def _generate(self, history: list[Message]) -> AgentResponse:
        """Review code and produce a PASS/FAIL verdict.

        Args:
            history: Message history (latest message is code to review).

        Returns:
            AgentResponse with passed=True if review passes.
        """
        prompt = history[-1].content if history else ""
        text = self._llm.generate("Reviewer", prompt)
        passed = text.upper().startswith("PASS")
        return AgentResponse(
            text=text,
            passed=passed,
            metadata={"stage": "review"},
        )
