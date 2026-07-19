import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.orchestrator import WorkflowManager


class TestWorkflowManager(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_analyzer = MagicMock()
        self.mock_synth = MagicMock()
        self.mock_guard = MagicMock()
        self.mock_auditor = MagicMock()
        self.mock_evolution = MagicMock()

        with patch("src.orchestrator.AppConfig") as MockConfig:
            mock_cfg = MagicMock()
            mock_cfg.settings.context_file = "CONTEXT.md"
            MockConfig.load.return_value = mock_cfg
            self.wm = WorkflowManager(
                self.mock_llm, self.mock_analyzer, self.mock_synth,
                self.mock_guard, self.mock_auditor, self.mock_evolution,
                config_path=".ai-sync.json"
            )

    def test_run_flow_design_rejection(self):
        self.mock_llm.generate.return_value = "Design doc with [TASK-1]"
        result = self.wm.run_flow("test task", lambda: False, initial_context="ctx")
        self.assertIn("rejected", result)

    def test_run_flow_invalid_json_returns_error(self):
        self.mock_llm.generate.return_value = "No JSON here"
        result = self.wm.run_flow("test task", lambda: True, initial_context="ctx")
        self.assertIn("decomposition", result.lower()) or self.assertIn("Design", result)

    def test_single_shot_implement_no_files(self):
        self.mock_llm.generate.return_value = ""
        result = self.wm._single_shot_implement("T1", "desc", [])
        self.assertIn("Error", result)

    def test_build_design_prompt_contains_task(self):
        prompt = self.wm._build_design_prompt("my task", "context")
        self.assertIn("my task", prompt)
        self.assertIn("context", prompt)


if __name__ == "__main__":
    unittest.main()
