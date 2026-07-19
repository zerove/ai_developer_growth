"""Parallel fan-out orchestrator: run multiple agents simultaneously."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from src.config import WorkflowConfig
from src.errors import AgentFailureError
from src.protocol import Agent, AgentResponse, Message, MessageRole


@dataclass
class FanOutResult:
    """Result from a parallel fan-out execution.

    Attributes:
        responses: Map of role -> AgentResponse for each agent that ran.
        history: Accumulated message history after fan-out.
        errors: Map of role -> error message for any agents that failed.
    """

    responses: dict[MessageRole, AgentResponse] = field(default_factory=dict)
    history: list[Message] = field(default_factory=list)
    errors: dict[MessageRole, str] = field(default_factory=dict)

    @property
    def all_succeeded(self) -> bool:
        """Whether all agents completed without errors."""
        return len(self.errors) == 0


class FanOutOrchestrator:
    """Run multiple agents in parallel on the same input.

    Useful for scenarios where independent analyses can happen concurrently,
    e.g. having the Architect and a Security Reviewer both analyze a PRD.

    Attributes:
        _agents: List of agents to fan out to.
        _config: Workflow configuration.
    """

    def __init__(
        self,
        agents: list[Agent],
        config: WorkflowConfig | None = None,
    ) -> None:
        self._agents = agents
        self._config = config or WorkflowConfig()

    def execute(
        self,
        history: list[Message],
        max_workers: int | None = None,
    ) -> FanOutResult:
        """Run all agents in parallel on the given history.

        Args:
            history: Shared message history to pass to each agent.
            max_workers: Max parallel threads (None = default to os cpu count).

        Returns:
            FanOutResult with all responses and any errors.

        Raises:
            AgentFailureError: If fail_fast=True and any agent fails.
        """
        result = FanOutResult(history=list(history))

        if not self._agents:
            return result

        max_workers = max_workers or min(len(self._agents), 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_agent = {
                executor.submit(agent.run, list(history)): agent
                for agent in self._agents
            }

            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    response = future.result()
                    result.responses[agent.role] = response
                except Exception as exc:
                    error_msg = f"Agent {agent.role.value} failed: {exc}"
                    result.errors[agent.role] = error_msg
                    if self._config.fail_fast:
                        raise AgentFailureError(
                            error_msg,
                            agent_role=agent.role.value,
                            cause=exc,
                        ) from exc

        # Append all successful responses to history
        for role, response in result.responses.items():
            result.history.append(Message(role=role, content=response.text))

        return result

    def execute_sequential(
        self,
        history: list[Message],
    ) -> FanOutResult:
        """Run agents sequentially as a fallback (for debugging/testing).

        Args:
            history: Shared message history.

        Returns:
            FanOutResult with all responses.
        """
        result = FanOutResult(history=list(history))

        for agent in self._agents:
            try:
                response = agent.run(list(history))
                result.responses[agent.role] = response
            except Exception as exc:
                error_msg = f"Agent {agent.role.value} failed: {exc}"
                result.errors[agent.role] = error_msg
                if self._config.fail_fast:
                    raise AgentFailureError(
                        error_msg,
                        agent_role=agent.role.value,
                        cause=exc,
                    ) from exc

        for role, response in result.responses.items():
            result.history.append(Message(role=role, content=response.text))

        return result
