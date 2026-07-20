"""Waterfall orchestrator: serial PM -> Architect -> (Coder <-> Reviewer loop)."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import WorkflowConfig
from errors import AgentFailureError, MaxIterationsError
from protocol import Agent, AgentResponse, Message, MessageRole


@dataclass
class WorkflowResult:
    """Result of a completed workflow execution.

    Attributes:
        history: Full message history after workflow completion.
        iterations: Number of Coder-Reviewer iterations performed.
        success: Whether the workflow completed successfully.
        error: Error message if the workflow failed, else None.
    """

    history: list[Message] = field(default_factory=list)
    iterations: int = 0
    success: bool = False
    error: str | None = None


class WaterfallOrchestrator:
    """Serial orchestrator: PM -> Architect -> Coder <-> Reviewer loop.

    This preserves the original demo behavior with proper typing and
    error handling. The workflow proceeds in strict sequence:
      1. PM produces PRD
      2. Architect produces design
      3. Coder writes code (loop start)
      4. Reviewer reviews code
      5. If FAIL: back to step 3 with "FIX: <feedback>"
      6. If PASS or max iterations: done

    Attributes:
        _agents: Dict mapping role to agent instance.
        _config: Workflow configuration.
    """

    def __init__(
        self,
        agents: dict[MessageRole, Agent],
        config: WorkflowConfig | None = None,
    ) -> None:
        self._agents = agents
        self._config = config or WorkflowConfig()

    def execute(self, user_request: str) -> WorkflowResult:
        """Run the full waterfall workflow.

        Args:
            user_request: The initial user request string.

        Returns:
            WorkflowResult with the complete history and status.

        Raises:
            AgentFailureError: If an agent fails and fail_fast is True.
            MaxIterationsError: If max_review_iterations exceeded (when fail_fast).
        """
        history: list[Message] = [
            Message(role=MessageRole.USER, content=user_request)
        ]
        self._run_phase_pm(history)
        self._run_phase_architect(history)
        return self._run_coder_reviewer_loop(history)

    def _run_phase_pm(self, history: list[Message]) -> None:
        prd_response = self._run_agent(MessageRole.PM, history)
        history.append(Message(role=MessageRole.PM, content=prd_response.text))

    def _run_phase_architect(self, history: list[Message]) -> None:
        design_response = self._run_agent(MessageRole.ARCHITECT, history)
        history.append(
            Message(role=MessageRole.ARCHITECT, content=design_response.text)
        )

    def _run_coder_reviewer_loop(self, history: list[Message]) -> WorkflowResult:
        iterations = 0
        max_iter = self._config.max_review_iterations

        while iterations < max_iter:
            iterations += 1

            # Coder
            coder_response = self._run_agent(MessageRole.CODER, history)
            history.append(Message(role=MessageRole.CODER, content=coder_response.text))

            # Reviewer
            reviewer_response = self._run_agent(MessageRole.REVIEWER, history)
            history.append(
                Message(role=MessageRole.REVIEWER, content=reviewer_response.text)
            )

            if reviewer_response.passed:
                return WorkflowResult(
                    history=history,
                    iterations=iterations,
                    success=True,
                )

            # Feed back "FIX: <feedback>" for next iteration
            fix_msg = f"FIX: {reviewer_response.text}"
            history.append(
                Message(
                    role=MessageRole.USER,
                    content=fix_msg,
                    metadata={"purpose": "fix_request"},
                )
            )

        # Exhausted iterations
        error_msg = f"Max iterations ({max_iter}) reached without approval."
        if self._config.fail_fast:
            raise MaxIterationsError(
                error_msg,
                iterations=iterations,
            )
        return WorkflowResult(
            history=history,
            iterations=iterations,
            success=False,
            error=error_msg,
        )

    def _run_agent(self, role: MessageRole, history: list[Message]) -> AgentResponse:
        """Look up and run an agent, handling failures.

        Args:
            role: Which agent to run.
            history: Current message history.

        Returns:
            AgentResponse from the agent.

        Raises:
            AgentFailureError: If agent not found or execution fails (when fail_fast).
        """
        agent = self._agents.get(role)
        if agent is None:
            msg = f"No agent registered for role {role.value}"
            if self._config.fail_fast:
                raise AgentFailureError(msg, agent_role=role.value)
            return AgentResponse(text=f"[SKIPPED] {msg}", metadata={"skipped": "true"})
        return agent.run(history)
