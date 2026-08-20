import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.auditor import FeedbackManager
from src.evolution import EvolutionEngine
from src.llm_client import LLMClient


class TestEvolutionEngine(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock(spec=LLMClient)
        self.mock_feedback = MagicMock(spec=FeedbackManager)
        self.mock_feedback.history = []
        self.engine = EvolutionEngine(self.mock_llm, self.mock_feedback, "docs/specs")

    def test_empty_history_returns_no_candidates(self):
        self.mock_feedback.history = []
        result = self.engine.analyze_conflicts()
        self.assertEqual(result, [])

    def test_no_conflicts_when_below_threshold(self):
        self.mock_feedback.history = [
            {"rule_id": "R1", "status": "active", "message": "m1", "file_path": "a.py"},
            {"rule_id": "R1", "status": "active", "message": "m2", "file_path": "b.py"},
        ]
        result = self.engine.analyze_conflicts()
        self.assertEqual(result, [])

    def test_detects_high_override_ratio(self):
        self.mock_feedback.history = [
            {
                "rule_id": "R1",
                "status": "overridden",
                "message": "m1",
                "file_path": "a.py",
            },
            {
                "rule_id": "R1",
                "status": "overridden",
                "message": "m2",
                "file_path": "b.py",
            },
            {"rule_id": "R1", "status": "active", "message": "m3", "file_path": "c.py"},
        ]
        result = self.engine.analyze_conflicts()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["rule_id"], "R1")
        self.assertAlmostEqual(result[0]["ratio"], 2 / 3)

    def test_requires_minimum_occurrences(self):
        self.mock_feedback.history = [
            {
                "rule_id": "R1",
                "status": "overridden",
                "message": "m1",
                "file_path": "a.py",
            },
        ]
        result = self.engine.analyze_conflicts()
        self.assertEqual(result, [])

    def test_multiple_rules_analyzed_independently(self):
        self.mock_feedback.history = [
            {
                "rule_id": "R1",
                "status": "overridden",
                "message": "m1",
                "file_path": "a.py",
            },
            {
                "rule_id": "R1",
                "status": "overridden",
                "message": "m2",
                "file_path": "b.py",
            },
            {"rule_id": "R2", "status": "active", "message": "m3", "file_path": "c.py"},
            {"rule_id": "R2", "status": "active", "message": "m4", "file_path": "d.py"},
        ]
        result = self.engine.analyze_conflicts()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["rule_id"], "R1")

    def test_propose_evolution_calls_llm(self):
        candidate = {
            "rule_id": "R1",
            "ratio": 0.8,
            "total": 5,
            "overridden": 4,
            "examples": [{"message": "test", "file_path": "a.py"}],
        }
        self.mock_llm.generate.return_value = "Updated rule text"
        result = self.engine.propose_evolution(candidate)
        self.assertEqual(result, "Updated rule text")
        self.mock_llm.generate.assert_called_once()

    def test_propose_batch_evolution_calls_llm(self):
        candidates = [
            {
                "rule_id": "R1",
                "ratio": 0.8,
                "total": 5,
                "overridden": 4,
                "examples": [{"message": "test", "file_path": "a.py"}],
            }
        ]
        self.mock_llm.generate.return_value = "Batch update document"
        result = self.engine.propose_batch_evolution(candidates)
        self.assertEqual(result, "Batch update document")
        self.mock_llm.generate.assert_called_once()

    def test_propose_batch_empty_candidates(self):
        result = self.engine.propose_batch_evolution([])
        self.assertIn("No candidates", result)


if __name__ == "__main__":
    unittest.main()
