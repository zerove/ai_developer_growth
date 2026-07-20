"""Tests for orchestration modes (Waterfall and Fan-Out)."""

import unittest

from agents import ArchitectAgent, CoderAgent, MockLLM, PMAgent, ReviewerAgent
from config import WorkflowConfig
from errors import AgentFailureError, MaxIterationsError
from orchestration import FanOutOrchestrator, WaterfallOrchestrator
from orchestration.fan_out import FanOutResult
from orchestration.waterfall import WorkflowResult
from protocol import Agent, AgentResponse, Message, MessageRole


def _make_agents() -> dict[MessageRole, Agent]:
    """Create standard agent set with MockLLM."""
    llm = MockLLM()
    return {
        MessageRole.PM: PMAgent(llm=llm),
        MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
        MessageRole.CODER: CoderAgent(llm=llm),
        MessageRole.REVIEWER: ReviewerAgent(llm=llm),
    }


class TestWaterfallOrchestrator(unittest.TestCase):
    """Tests for WaterfallOrchestrator."""

    def test_full_happy_path(self) -> None:
        """PM -> Architect -> Coder -> Reviewer(PASS)."""
        agents = _make_agents()
        orch = WaterfallOrchestrator(agents=agents)
        result = orch.execute("Build a currency converter")

        self.assertTrue(result.success)
        # MockLLM reviewer FAILs first pass (no "error handling" in code),
        # then PASSes after the FIX message adds error handling.
        self.assertEqual(result.iterations, 2)
        self.assertIsNone(result.error)
        # USER + PM + ARCH + CODER1 + REV1 + FIX + CODER2 + REV2 = 8
        self.assertEqual(len(result.history), 8)
        roles = [m.role for m in result.history]
        self.assertIn(MessageRole.PM, roles)
        self.assertIn(MessageRole.ARCHITECT, roles)
        self.assertIn(MessageRole.CODER, roles)
        self.assertIn(MessageRole.REVIEWER, roles)

    def test_reviewer_loop(self) -> None:
        """FAIL -> FIX -> PASS loop."""
        agents = _make_agents()
        # Override reviewer to FAIL first, then PASS
        reviewer = agents[MessageRole.REVIEWER]
        call_count = [0]

        def reviewer_side_effect(history: list[Message]) -> AgentResponse:
            call_count[0] += 1
            last = history[-1].content if history else ""
            if "error handling" in last:
                return AgentResponse(text="PASS: Good.", passed=True)
            return AgentResponse(text="FAIL: Missing error handling.", passed=False)

        reviewer.run = reviewer_side_effect  # type: ignore[assignment]

        orch = WaterfallOrchestrator(agents=agents)
        result = orch.execute("Build a converter")

        self.assertTrue(result.success)
        self.assertEqual(result.iterations, 2)
        self.assertEqual(call_count[0], 2)

    def test_max_iterations_reached(self) -> None:
        """Exceed max_review_iterations raises MaxIterationsError."""
        agents = _make_agents()
        # Reviewer always FAILs
        reviewer = agents[MessageRole.REVIEWER]
        reviewer.run = lambda h: AgentResponse(  # type: ignore[assignment]
            text="FAIL: Always broken.", passed=False
        )

        config = WorkflowConfig(max_review_iterations=2, fail_fast=True)
        orch = WaterfallOrchestrator(agents=agents, config=config)

        with self.assertRaises(MaxIterationsError) as ctx:
            orch.execute("Build something")
        self.assertEqual(ctx.exception.iterations, 2)

    def test_max_iterations_no_fail_fast(self) -> None:
        """Without fail_fast, returns failed result instead of raising."""
        agents = _make_agents()
        reviewer = agents[MessageRole.REVIEWER]
        reviewer.run = lambda h: AgentResponse(  # type: ignore[assignment]
            text="FAIL", passed=False
        )

        config = WorkflowConfig(max_review_iterations=2, fail_fast=False)
        orch = WaterfallOrchestrator(agents=agents, config=config)
        result = orch.execute("Build something")

        self.assertFalse(result.success)
        self.assertIn("Max iterations", result.error or "")

    def test_missing_agent_no_fail_fast(self) -> None:
        """Missing agent returns skipped response when fail_fast=False."""
        agents = {MessageRole.PM: PMAgent()}
        config = WorkflowConfig(fail_fast=False)
        orch = WaterfallOrchestrator(agents=agents, config=config)
        result = orch.execute("Build something")

        self.assertFalse(result.success)
        self.assertIn("SKIPPED", result.history[-1].content)

    def test_missing_agent_fail_fast(self) -> None:
        """Missing agent raises AgentFailureError when fail_fast=True."""
        agents = {MessageRole.PM: PMAgent()}
        orch = WaterfallOrchestrator(agents=agents)
        with self.assertRaises(AgentFailureError):
            orch.execute("Build something")


class TestFanOutOrchestrator(unittest.TestCase):
    """Tests for FanOutOrchestrator."""

    def test_parallel_execution(self) -> None:
        """Multiple agents run and all succeed."""
        agents: list[Agent] = [PMAgent(), ArchitectAgent(), CoderAgent()]
        orch = FanOutOrchestrator(agents=agents)

        history = [Message(role=MessageRole.USER, content="Build a converter")]
        result = orch.execute(history, max_workers=2)

        self.assertTrue(result.all_succeeded)
        self.assertEqual(len(result.responses), 3)
        self.assertEqual(len(result.errors), 0)
        self.assertIn(MessageRole.PM, result.responses)
        self.assertIn(MessageRole.ARCHITECT, result.responses)
        self.assertIn(MessageRole.CODER, result.responses)

    def test_sequential_fallback(self) -> None:
        """execute_sequential runs agents in order."""
        agents: list[Agent] = [PMAgent(), ArchitectAgent()]
        orch = FanOutOrchestrator(agents=agents)

        history = [Message(role=MessageRole.USER, content="Build something")]
        result = orch.execute_sequential(history)

        self.assertTrue(result.all_succeeded)
        self.assertEqual(len(result.responses), 2)

    def test_agent_failure_fail_fast(self) -> None:
        """Failing agent raises when fail_fast=True."""
        good_agent = PMAgent()

        class BrokenAgent:
            @property
            def role(self) -> MessageRole:
                return MessageRole.CODER

            def run(self, history: list[Message]) -> AgentResponse:
                raise RuntimeError("boom")

        agents: list[Agent] = [good_agent, BrokenAgent()]  # type: ignore[list-item]
        config = WorkflowConfig(fail_fast=True)
        orch = FanOutOrchestrator(agents=agents, config=config)

        history = [Message(role=MessageRole.USER, content="test")]
        with self.assertRaises(AgentFailureError):
            orch.execute(history)

    def test_agent_failure_no_fail_fast(self) -> None:
        """Failing agent is recorded when fail_fast=False."""
        good_agent = PMAgent()

        class BrokenAgent:
            @property
            def role(self) -> MessageRole:
                return MessageRole.CODER

            def run(self, history: list[Message]) -> AgentResponse:
                raise RuntimeError("boom")

        agents: list[Agent] = [good_agent, BrokenAgent()]  # type: ignore[list-item]
        config = WorkflowConfig(fail_fast=False)
        orch = FanOutOrchestrator(agents=agents, config=config)

        history = [Message(role=MessageRole.USER, content="test")]
        result = orch.execute(history)

        self.assertFalse(result.all_succeeded)
        self.assertIn(MessageRole.CODER, result.errors)
        self.assertIn(MessageRole.PM, result.responses)

    def test_empty_agents(self) -> None:
        """No agents produces empty result."""
        orch = FanOutOrchestrator(agents=[])
        history = [Message(role=MessageRole.USER, content="test")]
        result = orch.execute(history)
        self.assertTrue(result.all_succeeded)
        self.assertEqual(len(result.responses), 0)


class TestWorkflowResult(unittest.TestCase):
    def test_defaults(self) -> None:
        result = WorkflowResult()
        self.assertFalse(result.success)
        self.assertEqual(result.iterations, 0)
        self.assertIsNone(result.error)
        self.assertEqual(result.history, [])


class TestFanOutResult(unittest.TestCase):
    def test_defaults(self) -> None:
        result = FanOutResult()
        self.assertTrue(result.all_succeeded)
        self.assertEqual(len(result.responses), 0)
        self.assertEqual(len(result.errors), 0)


if __name__ == "__main__":
    unittest.main()
