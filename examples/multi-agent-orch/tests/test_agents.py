"""Tests for agent implementations."""

import unittest

from agents import ArchitectAgent, CoderAgent, MockLLM, PMAgent, ReviewerAgent
from agents.base import BaseAgent
from config import AgentConfig
from errors import AgentFailureError
from protocol import AgentResponse, Message, MessageRole


class TestMockLLM(unittest.TestCase):
    """Tests for MockLLM.generate()."""

    def setUp(self) -> None:
        self.llm = MockLLM()

    def test_pm_role(self) -> None:
        result = self.llm.generate("PM", "Build a converter")
        self.assertIn("[PRD]", result)
        self.assertIn("Build a converter", result)
        self.assertIn("Goal:", result)

    def test_architect_role(self) -> None:
        result = self.llm.generate("Architect", "[PRD] Some PRD")
        self.assertIn("[Design]", result)
        self.assertIn("CurrencyConverter", result)

    def test_coder_default(self) -> None:
        result = self.llm.generate("Coder", "Some design")
        self.assertIn("def convert(", result)
        self.assertIn("rate = 1.1", result)

    def test_coder_fix(self) -> None:
        result = self.llm.generate("Coder", "FIX: add error handling")
        self.assertIn("try:", result)
        self.assertIn("Fixed:", result)

    def test_reviewer_fail(self) -> None:
        result = self.llm.generate("Reviewer", "some code")
        self.assertIn("FAIL", result)

    def test_reviewer_pass(self) -> None:
        result = self.llm.generate("Reviewer", "code with error handling")
        self.assertTrue(result.startswith("PASS"))

    def test_unknown_role(self) -> None:
        result = self.llm.generate("Unknown", "hello")
        self.assertIn("don't know", result)


class TestBaseAgent(unittest.TestCase):
    """Tests for BaseAgent ABC behavior."""

    def test_run_wraps_exceptions(self) -> None:
        class BrokenAgent(BaseAgent):
            _role = MessageRole.PM

            def _generate(self, history: list[Message]) -> AgentResponse:
                raise ValueError("internal error")

        agent = BrokenAgent()
        with self.assertRaises(AgentFailureError) as ctx:
            agent.run([])
        self.assertIn("failed", str(ctx.exception))
        self.assertIsNotNone(ctx.exception.cause)

    def test_run_passes_through_agent_errors(self) -> None:
        class DirectFailAgent(BaseAgent):
            _role = MessageRole.CODER

            def _generate(self, history: list[Message]) -> AgentResponse:
                raise AgentFailureError("direct fail", agent_role="CODER")

        agent = DirectFailAgent()
        with self.assertRaises(AgentFailureError):
            agent.run([])


class TestPMAgent(unittest.TestCase):
    def test_role(self) -> None:
        agent = PMAgent()
        self.assertEqual(agent.role, MessageRole.PM)

    def test_run_produces_prd(self) -> None:
        agent = PMAgent()
        history = [Message(role=MessageRole.USER, content="Build a converter")]
        response = agent.run(history)
        self.assertIn("[PRD]", response.text)
        self.assertEqual(response.metadata["stage"], "prd")

    def test_empty_history(self) -> None:
        agent = PMAgent()
        response = agent.run([])
        self.assertIn("[PRD]", response.text)


class TestArchitectAgent(unittest.TestCase):
    def test_role(self) -> None:
        agent = ArchitectAgent()
        self.assertEqual(agent.role, MessageRole.ARCHITECT)

    def test_run_produces_design(self) -> None:
        agent = ArchitectAgent()
        history = [
            Message(role=MessageRole.USER, content="Build a converter"),
            Message(role=MessageRole.PM, content="[PRD] requirements..."),
        ]
        response = agent.run(history)
        self.assertIn("[Design]", response.text)
        self.assertEqual(response.metadata["stage"], "design")


class TestCoderAgent(unittest.TestCase):
    def test_role(self) -> None:
        agent = CoderAgent()
        self.assertEqual(agent.role, MessageRole.CODER)

    def test_run_produces_code(self) -> None:
        agent = CoderAgent()
        history = [Message(role=MessageRole.ARCHITECT, content="[Design] build this")]
        response = agent.run(history)
        self.assertIn("def convert(", response.text)
        self.assertEqual(response.metadata["stage"], "code")


class TestReviewerAgent(unittest.TestCase):
    def test_role(self) -> None:
        agent = ReviewerAgent()
        self.assertEqual(agent.role, MessageRole.REVIEWER)

    def test_fail_sets_passed_false(self) -> None:
        agent = ReviewerAgent()
        history = [Message(role=MessageRole.CODER, content="some code")]
        response = agent.run(history)
        self.assertFalse(response.passed)
        self.assertIn("FAIL", response.text)

    def test_pass_sets_passed_true(self) -> None:
        agent = ReviewerAgent()
        history = [Message(role=MessageRole.CODER, content="code with error handling")]
        response = agent.run(history)
        self.assertTrue(response.passed)
        self.assertTrue(response.text.startswith("PASS"))

    def test_metadata(self) -> None:
        agent = ReviewerAgent()
        history = [Message(role=MessageRole.CODER, content="code")]
        response = agent.run(history)
        self.assertEqual(response.metadata["stage"], "review")


class TestAgentProtocolCompliance(unittest.TestCase):
    """Verify all agents satisfy the Agent protocol."""

    def test_all_agents_satisfy_protocol(self) -> None:
        from protocol import Agent

        agents = [PMAgent(), ArchitectAgent(), CoderAgent(), ReviewerAgent()]
        for agent in agents:
            name = type(agent).__name__
            self.assertIsInstance(agent, Agent, f"{name} fails protocol")

    def test_custom_config(self) -> None:
        config = AgentConfig(role="PM", timeout=10.0, custom_prompt="Be concise")
        agent = PMAgent(config=config)
        self.assertEqual(agent.config.timeout, 10.0)
        self.assertEqual(agent.config.custom_prompt, "Be concise")


if __name__ == "__main__":
    unittest.main()
