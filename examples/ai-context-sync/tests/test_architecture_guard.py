import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.guard import ArchitectureGuard
from src.llm_client import LLMClient

class TestArchitectureGuard(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=LLMClient)
        self.guard = ArchitectureGuard(self.mock_client, "docs/adr/")

    def test_check_drift_json_returns_violations(self):
        mock_violations = '[{"rule_id": "ADR-001", "severity": "Critical", "description": "Violation detected", "adr_file": "docs/adr/001.md"}]'
        self.mock_client.generate.return_value = mock_violations
        
        self.guard._load_adrs = MagicMock(return_value="ADR-001: Use PostgreSQL")
        report = self.guard.check_drift_json("diff", "msg")
        
        self.assertIsInstance(report, list)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["rule_id"], "ADR-001")

if __name__ == "__main__":
    unittest.main()
