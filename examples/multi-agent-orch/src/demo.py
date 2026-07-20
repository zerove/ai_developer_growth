"""Multi-agent workflow demo - demonstrates both orchestration modes.

Usage:
    python -m src.demo                    # Run both modes
    python -m src.demo --mode waterfall   # Waterfall only
    python -m src.demo --mode fan-out     # Fan-out only
"""

from __future__ import annotations

import argparse

from agents import (
    ArchitectAgent,
    CoderAgent,
    MockLLM,
    PMAgent,
    ReviewerAgent,
)
from config import WorkflowConfig
from orchestration import FanOutOrchestrator, WaterfallOrchestrator
from protocol import Message, MessageRole


def _print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_step(role: str, content: str) -> None:
    print(f"\n[{role}]")
    print(f"{'-' * 40}")
    print(content)


def run_waterfall(request: str) -> None:
    """Run the serial waterfall workflow."""
    _print_header("Waterfall Mode: PM -> Architect -> Coder <-> Reviewer")

    llm = MockLLM()
    agents = {
        MessageRole.PM: PMAgent(llm=llm),
        MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
        MessageRole.CODER: CoderAgent(llm=llm),
        MessageRole.REVIEWER: ReviewerAgent(llm=llm),
    }
    config = WorkflowConfig(mode="waterfall", max_review_iterations=3)
    orchestrator = WaterfallOrchestrator(agents=agents, config=config)

    result = orchestrator.execute(request)

    # Print summary
    for msg in result.history:
        if msg.role != MessageRole.USER:
            _print_step(msg.role.value, msg.content)

    print(f"\n{'=' * 60}")
    status = "SUCCESS" if result.success else "FAILED"
    print(f"  Workflow {status} | Iterations: {result.iterations}")
    print(f"{'=' * 60}")


def run_fan_out(request: str) -> None:
    """Run parallel agents on the same input."""
    _print_header("Fan-Out Mode: Parallel Agent Execution")

    llm = MockLLM()
    agents = [
        PMAgent(llm=llm),
        ArchitectAgent(llm=llm),
        CoderAgent(llm=llm),
    ]
    config = WorkflowConfig(mode="parallel-fan-out")
    orchestrator = FanOutOrchestrator(agents=agents, config=config)

    initial_history = [
        Message(role=MessageRole.USER, content=request),
    ]
    result = orchestrator.execute(initial_history)

    for role, response in result.responses.items():
        _print_step(role.value, response.text)

    print(f"\n{'=' * 60}")
    print(f"  Fan-Out {result.all_succeeded and 'SUCCESS' or 'PARTIAL'}")
    print(f"  Agents: {len(result.responses)} | Errors: {len(result.errors)}")
    print(f"{'=' * 60}")


def main() -> None:
    """Entry point for the demo."""
    parser = argparse.ArgumentParser(description="Multi-agent workflow demo")
    parser.add_argument(
        "--mode",
        choices=["waterfall", "fan-out", "both"],
        default="both",
        help="Orchestration mode (default: both)",
    )
    parser.add_argument(
        "--request",
        default="Build a simple currency converter",
        help="User request to process",
    )
    args = parser.parse_args()

    if args.mode in ("waterfall", "both"):
        run_waterfall(args.request)
    if args.mode in ("fan-out", "both"):
        run_fan_out(args.request)


if __name__ == "__main__":
    main()
