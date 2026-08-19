"""Configuration dataclasses for agents and workflows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Configuration for a single agent instance.

    Attributes:
        role: The role name (e.g. "PM", "Architect").
        timeout: Maximum seconds the agent can take to respond.
        max_retries: How many times to retry on transient failures.
        temperature: LLM temperature parameter (0.0-1.0).
        custom_prompt: Optional system prompt override for this agent.
    """

    role: str
    timeout: float = 30.0
    max_retries: int = 2
    temperature: float = 0.7
    custom_prompt: str = ""


@dataclass
class WorkflowConfig:
    """Configuration for workflow orchestration.

    Attributes:
        mode: Orchestration mode ("waterfall" or "parallel-fan-out").
        max_review_iterations: Max Coder-Reviewer loop iterations before forcing stop.
        agent_configs: Per-agent configuration overrides.
        fail_fast: If True, stop workflow on first agent failure.
    """

    mode: str = "waterfall"
    max_review_iterations: int = 3
    agent_configs: dict[str, AgentConfig] = field(default_factory=dict)
    fail_fast: bool = True
