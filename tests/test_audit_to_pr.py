import unittest
import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'tools', 'scripts'))
from audit_to_pr import format_audit_results

class TestAuditToPr(unittest.TestCase):
    def test_empty_violations(self):
        """Test formatting with no violations."""
        json_input = "[]"
        result = format_audit_results(json_input)
        self.assertIn("No specification violations detected", result)
        self.assertIn("Great job!", result)

    def test_invalid_json(self):
        """Test handling of invalid JSON input."""
        json_input = "not valid json"
        result = format_audit_results(json_input)
        self.assertIn("Error: Invalid JSON input", result)

    def test_single_violation(self):
        """Test formatting with a single violation."""
        violations = [
            {
                "rule_id": "TEST-001",
                "severity": "Critical",
                "message": "Test violation",
                "file": "test.py",
                "line": 10
            }
        ]
        json_input = json.dumps(violations)
        result = format_audit_results(json_input)
        self.assertIn("**1** specification violations", result)
        self.assertIn("Critical", result)
        self.assertIn("TEST-001", result)
        self.assertIn("Test violation", result)

    def test_multiple_violations(self):
        """Test formatting with multiple violations of different severities."""
        violations = [
            {
                "rule_id": "TEST-001",
                "severity": "Critical",
                "message": "Critical violation",
                "file": "test.py",
                "line": 10
            },
            {
                "rule_id": "TEST-002",
                "severity": "Warning",
                "message": "Warning violation",
                "file": "test2.py",
                "line": 20
            },
            {
                "rule_id": "TEST-003",
                "severity": "Info",
                "message": "Info violation",
                "file": "test3.py",
                "line": 30
            }
        ]
        json_input = json.dumps(violations)
        result = format_audit_results(json_input)
        self.assertIn("**3** specification violations", result)
        self.assertIn("**Critical**: 1", result)
        self.assertIn("**Warning**: 1", result)
        self.assertIn("**Info**: 1", result)

if __name__ == "__main__":
    unittest.main()
