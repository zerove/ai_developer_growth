"""Tests for examples/multi-agent-orch/demo.py"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path so we can import demo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from demo import MockLLM, Agent, WorkflowOrchestrator


class TestMockLLM(unittest.TestCase):
    """Tests for MockLLM.generate()."""

    def setUp(self):
        self.llm = MockLLM()

    def test_pm_role(self):
        result = self.llm.generate("PM", "Build a converter")
        self.assertIn("[PRD]", result)
        self.assertIn("Build a converter", result)
        self.assertIn("Goal:", result)

    def test_architect_role(self):
        result = self.llm.generate("Architect", "[PRD] Some PRD")
        self.assertIn("[Design]", result)
        self.assertIn("CurrencyConverter", result)
        self.assertIn("convert(amount, from_curr, to_curr)", result)

    def test_coder_role_default(self):
        result = self.llm.generate("Coder", "Some design")
        self.assertIn("def convert(", result)
        self.assertIn("rate = 1.1", result)

    def test_coder_role_fix_prompt(self):
        result = self.llm.generate("Coder", "FIX: add error handling")
        self.assertIn("def convert(", result)
        self.assertIn("Fixed: Added error handling", result)
        self.assertIn("try:", result)

    def test_reviewer_role_fail(self):
        result = self.llm.generate("Reviewer", "some code")
        self.assertIn("FAIL", result)
        self.assertIn("Missing error handling", result)

    def test_reviewer_role_pass(self):
        result = self.llm.generate("Reviewer", "code with error handling")
        self.assertEqual(result, "PASS: Code looks good now.")

    def test_unknown_role(self):
        result = self.llm.generate("Unknown", "hello")
        self.assertIn("don't know", result)


class TestAgent(unittest.TestCase):
    """Tests for Agent class."""

    def setUp(self):
        self.llm = MockLLM()

    def test_init_sets_role_and_llm(self):
        agent = Agent("PM", self.llm)
        self.assertEqual(agent.role, "PM")
        self.assertIs(agent.llm, self.llm)

    def test_init_coder(self):
        agent = Agent("Coder", self.llm)
        self.assertEqual(agent.role, "Coder")

    @patch("demo.time.sleep")
    @patch("builtins.print")
    def test_run_calls_llm_with_role(self, mock_print, mock_sleep):
        agent = Agent("PM", self.llm)
        result = agent.run("Build a tool")
        # Verify it returns the PM output
        self.assertIn("[PRD]", result)
        self.assertIn("Build a tool", result)
        # Verify time.sleep was called (simulating thinking)
        mock_sleep.assert_called_once_with(0.5)

    @patch("demo.time.sleep")
    @patch("builtins.print")
    def test_run_coder(self, mock_print, mock_sleep):
        agent = Agent("Coder", self.llm)
        result = agent.run("write code")
        self.assertIn("def convert(", result)


class TestWorkflowOrchestrator(unittest.TestCase):
    """Tests for WorkflowOrchestrator class."""

    def test_init_creates_all_agents(self):
        orch = WorkflowOrchestrator()
        self.assertIsInstance(orch.llm, MockLLM)
        self.assertIsInstance(orch.pm, Agent)
        self.assertIsInstance(orch.architect, Agent)
        self.assertIsInstance(orch.coder, Agent)
        self.assertIsInstance(orch.reviewer, Agent)
        # Verify roles
        self.assertEqual(orch.pm.role, "PM")
        self.assertEqual(orch.architect.role, "Architect")
        self.assertEqual(orch.coder.role, "Coder")
        self.assertEqual(orch.reviewer.role, "Reviewer")
        # Verify all agents share the same LLM
        self.assertIs(orch.pm.llm, orch.llm)
        self.assertIs(orch.architect.llm, orch.llm)

    @patch("demo.time.sleep")
    @patch("builtins.print")
    def test_execute_full_workflow(self, mock_print, mock_sleep):
        """Test the happy path: PM -> Architect -> Coder -> Reviewer(PASS)."""
        orch = WorkflowOrchestrator()
        mock_pm = patch.object(orch.pm, "run", return_value="[PRD] Test PRD")
        mock_arch = patch.object(orch.architect, "run", return_value="[Design] Test Design")
        mock_coder = patch.object(orch.coder, "run", return_value="def convert(): pass")
        mock_review = patch.object(orch.reviewer, "run", return_value="PASS: Looks good.")

        m_pm = mock_pm.start()
        m_arch = mock_arch.start()
        m_coder = mock_coder.start()
        m_review = mock_review.start()
        try:
            orch.execute("Build a converter")
            m_pm.assert_called_once()
            m_arch.assert_called_once()
            m_coder.assert_called_once()
            m_review.assert_called_once()
        finally:
            mock_pm.stop()
            mock_arch.stop()
            mock_coder.stop()
            mock_review.stop()

    @patch("demo.time.sleep")
    @patch("builtins.print")
    def test_execute_max_iterations(self, mock_print, mock_sleep):
        """Test that workflow stops after max iterations (iteration > 3)."""
        orch = WorkflowOrchestrator()
        # Patch all agents; reviewer always FAILS
        mock_pm = patch.object(orch.pm, "run", return_value="[PRD] Test")
        mock_arch = patch.object(orch.architect, "run", return_value="[Design] Test")
        mock_coder = patch.object(orch.coder, "run", return_value="def code(): pass")
        mock_review = patch.object(orch.reviewer, "run", return_value="FAIL: Still broken.")

        m_pm = mock_pm.start()
        m_arch = mock_arch.start()
        m_coder = mock_coder.start()
        m_review = mock_review.start()
        try:
            orch.execute("Build something")
            # Iterations 1, 2, 3 (each fails, iter > 3 breaks at 4)
            self.assertEqual(m_coder.call_count, 3)
        finally:
            mock_pm.stop()
            mock_arch.stop()
            mock_coder.stop()
            mock_review.stop()

    @patch("demo.time.sleep")
    @patch("builtins.print")
    def test_execute_prints_workflow_stages(self, mock_print, mock_sleep):
        """Test that execute prints output from each stage."""
        orch = WorkflowOrchestrator()
        with patch.object(orch.reviewer, "run", return_value="PASS: OK"):
            orch.execute("Build a tool")

        # Check that print was called with stage labels
        printed_args = [call.args[0] for call in mock_print.call_args_list]
        self.assertTrue(any("PM Output" in arg for arg in printed_args))
        self.assertTrue(any("Architect Output" in arg for arg in printed_args))
        self.assertTrue(any("Code:" in arg for arg in printed_args))
        self.assertTrue(any("Reviewer Feedback" in arg for arg in printed_args))
        self.assertTrue(any("Workflow Completed" in arg for arg in printed_args))


if __name__ == "__main__":
    unittest.main()
