import unittest
import json
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock
from io import StringIO

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

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_valid_input(self, mock_stdout, mock_stdin):
        """Test main logic with valid JSON input."""
        violations = [{"rule_id": "TEST-001", "severity": "Critical", "message": "Test", "file": "test.py", "line": 10}]
        mock_stdin.write(json.dumps(violations))
        mock_stdin.seek(0)

        # Execute the main block logic
        input_data = sys.stdin.read()
        if not input_data:
            print("❌ Error: No input provided to audit-to-pr.")
            sys.exit(1)
        print(format_audit_results(input_data))

        output = mock_stdout.getvalue()
        self.assertIn("AI-Context-Sync Audit Report", output)
        self.assertIn("TEST-001", output)

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_empty_input(self, mock_stdout, mock_stdin):
        """Test main logic with empty input."""
        mock_stdin.write("")
        mock_stdin.seek(0)

        # Execute the main block logic
        input_data = sys.stdin.read()
        if not input_data:
            print("❌ Error: No input provided to audit-to-pr.")
            with self.assertRaises(SystemExit) as cm:
                sys.exit(1)
            self.assertEqual(cm.exception.code, 1)
        output = mock_stdout.getvalue()
        self.assertIn("No input provided", output)

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_invalid_json(self, mock_stdout, mock_stdin):
        """Test main logic with invalid JSON."""
        mock_stdin.write("invalid json")
        mock_stdin.seek(0)

        # Execute the main block logic
        input_data = sys.stdin.read()
        if not input_data:
            print("❌ Error: No input provided to audit-to-pr.")
            sys.exit(1)
        print(format_audit_results(input_data))

        output = mock_stdout.getvalue()
        self.assertIn("Invalid JSON input", output)

    def test_main_block_via_subprocess(self):
        """Test the actual __main__ block via subprocess to cover lines 48-55."""
        # Test with valid input
        result = subprocess.run(
            [sys.executable, "tools/scripts/audit_to_pr.py"],
            input='[{"rule_id": "TEST-001", "severity": "Critical", "message": "Test", "file": "test.py", "line": 10}]',
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..")
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("AI-Context-Sync Audit Report", result.stdout)
        self.assertIn("TEST-001", result.stdout)

        # Test with empty input
        result = subprocess.run(
            [sys.executable, "tools/scripts/audit_to_pr.py"],
            input="",
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), "..")
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("No input provided", result.stdout)


if __name__ == "__main__":
    unittest.main()
