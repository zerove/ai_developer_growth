"""Integration tests for the complete multi-agent workflow."""

import unittest

from multi_agent_orch import (
    ArchitectAgent,
    CoderAgent,
    MockLLM,
    PMAgent,
    ReviewerAgent,
)
from multi_agent_orch.config import WorkflowConfig
from multi_agent_orch.errors import MaxIterationsError
from multi_agent_orch.orchestration import FanOutOrchestrator, WaterfallOrchestrator
from multi_agent_orch.protocol import Message, MessageRole


class TestWaterfallIntegration(unittest.TestCase):
    """End-to-end tests using real agents with MockLLM."""

    def test_complete_workflow_mock(self) -> None:
        """Full workflow with MockLLM: PM -> Architect -> Coder -> Reviewer."""
        llm = MockLLM()
        agents = {
            MessageRole.PM: PMAgent(llm=llm),
            MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
            MessageRole.CODER: CoderAgent(llm=llm),
            MessageRole.REVIEWER: ReviewerAgent(llm=llm),
        }
        orch = WaterfallOrchestrator(agents=agents)
        result = orch.execute("Build a currency converter")

        self.assertTrue(result.success)
        # MockLLM reviewer FAILs first pass, PASSes on FIX iteration.
        self.assertEqual(result.iterations, 2)

        # Verify message content at each stage
        pm_msg = next(m for m in result.history if m.role == MessageRole.PM)
        self.assertIn("[PRD]", pm_msg.content)

        arch_msg = next(m for m in result.history if m.role == MessageRole.ARCHITECT)
        self.assertIn("[Design]", arch_msg.content)

        coder_msg = next(m for m in result.history if m.role == MessageRole.CODER)
        self.assertIn("def convert(", coder_msg.content)

        reviewer_msgs = [m for m in result.history if m.role == MessageRole.REVIEWER]
        self.assertTrue(reviewer_msgs[-1].content.startswith("PASS"))

    def test_iterative_fix_loop(self) -> None:
        """Reviewer FAILs first time, PASSes after fix."""
        llm = MockLLM()
        agents = {
            MessageRole.PM: PMAgent(llm=llm),
            MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
            MessageRole.CODER: CoderAgent(llm=llm),
            MessageRole.REVIEWER: ReviewerAgent(llm=llm),
        }
        orch = WaterfallOrchestrator(agents=agents)
        result = orch.execute("Build a converter")

        # MockLLM reviewer FAILs first, then the coder gets "FIX:" prefix
        # which triggers the "error handling" path, so reviewer PASSes on iter 2
        self.assertTrue(result.success)
        self.assertEqual(result.iterations, 2)

        # Verify FIX message was inserted
        fix_msgs = [
            m for m in result.history if m.metadata.get("purpose") == "fix_request"
        ]
        self.assertEqual(len(fix_msgs), 1)
        self.assertIn("FIX:", fix_msgs[0].content)

    def test_all_roles_present_in_history(self) -> None:
        """Every expected role appears at least once in the final history."""
        llm = MockLLM()
        agents = {
            MessageRole.PM: PMAgent(llm=llm),
            MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
            MessageRole.CODER: CoderAgent(llm=llm),
            MessageRole.REVIEWER: ReviewerAgent(llm=llm),
        }
        orch = WaterfallOrchestrator(agents=agents)
        result = orch.execute("Build a tool")

        found_roles = {m.role for m in result.history}
        expected = {
            MessageRole.PM,
            MessageRole.ARCHITECT,
            MessageRole.CODER,
            MessageRole.REVIEWER,
        }
        self.assertTrue(expected.issubset(found_roles))

    def test_max_iterations_integration(self) -> None:
        """Workflow stops at max iterations with real agents."""
        llm = MockLLM()
        agents = {
            MessageRole.PM: PMAgent(llm=llm),
            MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
            MessageRole.CODER: CoderAgent(llm=llm),
            MessageRole.REVIEWER: ReviewerAgent(llm=llm),
        }
        config = WorkflowConfig(max_review_iterations=1, fail_fast=True)
        orch = WaterfallOrchestrator(agents=agents, config=config)

        with self.assertRaises(MaxIterationsError):
            orch.execute("Build a tool")


class TestFanOutIntegration(unittest.TestCase):
    """End-to-end fan-out tests."""

    def test_parallel_agents_all_produce_output(self) -> None:
        llm = MockLLM()
        agents = [PMAgent(llm=llm), ArchitectAgent(llm=llm), CoderAgent(llm=llm)]
        orch = FanOutOrchestrator(agents=agents)

        history = [Message(role=MessageRole.USER, content="Build a converter")]
        result = orch.execute(history)

        self.assertTrue(result.all_succeeded)
        self.assertEqual(len(result.responses), 3)

        # Each agent produces role-appropriate content
        self.assertIn("[PRD]", result.responses[MessageRole.PM].text)
        self.assertIn("[Design]", result.responses[MessageRole.ARCHITECT].text)
        self.assertIn("def convert(", result.responses[MessageRole.CODER].text)

    def test_sequential_and_parallel_same_results(self) -> None:
        """Both execution modes produce the same output content."""
        llm = MockLLM()
        agents = [PMAgent(llm=llm), ArchitectAgent(llm=llm)]
        orch = FanOutOrchestrator(agents=agents)

        history = [Message(role=MessageRole.USER, content="Build a tool")]
        parallel_result = orch.execute(history)
        sequential_result = orch.execute_sequential(history)

        for role in [MessageRole.PM, MessageRole.ARCHITECT]:
            self.assertEqual(
                parallel_result.responses[role].text,
                sequential_result.responses[role].text,
            )


if __name__ == "__main__":
    unittest.main()
