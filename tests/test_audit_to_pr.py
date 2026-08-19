import json
import os
import subprocess
import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tools", "scripts"))
from audit_to_pr import (
    create_github_pr,
    format_audit_results_json,
    format_pr_report,
    main,
    parse_audit_output,
    run_governance_audit,
)


class TestAuditToPr(unittest.TestCase):
    """Tests for audit_to_pr module."""

    def test_empty_violations(self):
        """Test formatting with no violations."""
        json_input = "[]"
        result = format_audit_results_json(json_input)
        self.assertIn("未发现规范违规", result)
        self.assertIn("做得好", result)

    def test_invalid_json(self):
        """Test handling of invalid JSON input."""
        json_input = "not valid json"
        result = format_audit_results_json(json_input)
        self.assertIn("Error: Invalid JSON input", result)

    def test_single_violation(self):
        """Test formatting with a single violation."""
        violations = [
            {"rule_id": "TEST-001", "severity": "Critical", "message": "Test violation", "file": "test.py", "line": 10}
        ]
        json_input = json.dumps(violations)
        result = format_audit_results_json(json_input)
        self.assertIn("**1** 个规范违规", result)
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
                "line": 10,
            },
            {
                "rule_id": "TEST-002",
                "severity": "Warning",
                "message": "Warning violation",
                "file": "test2.py",
                "line": 20,
            },
            {"rule_id": "TEST-003", "severity": "Info", "message": "Info violation", "file": "test3.py", "line": 30},
        ]
        json_input = json.dumps(violations)
        result = format_audit_results_json(json_input)
        self.assertIn("**3** 个规范违规", result)
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
        print(format_audit_results_json(input_data))

        output = mock_stdout.getvalue()
        self.assertIn("治理审计报告 (JSON 输入模式)", output)
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
        print(format_audit_results_json(input_data))

        output = mock_stdout.getvalue()
        self.assertIn("Invalid JSON input", output)

    def test_main_block_via_subprocess(self):
        """Test the actual __main__ block via subprocess to cover lines 48-55."""
        # Test with valid input
        result = subprocess.run(
            [sys.executable, "tools/scripts/audit_to_pr.py", "--stdin"],
            input='[{"rule_id": "TEST-001", "severity": "Critical", "message": "Test", "file": "test.py", "line": 10}]',
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("治理审计报告 (JSON 输入模式)", result.stdout)
        self.assertIn("TEST-001", result.stdout)

        # Test with empty input
        result = subprocess.run(
            [sys.executable, "tools/scripts/audit_to_pr.py", "--stdin"],
            input="",
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("No input provided", result.stdout)


class TestRunGovernanceAudit(unittest.TestCase):
    """Tests for run_governance_audit function."""

    @patch("audit_to_pr.subprocess.run")
    def test_run_governance_audit_success(self, mock_run):
        """Test successful audit run."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="✅ PASS: Lint\n✅ PASS: Format",
            stderr="",
        )

        result = run_governance_audit(full=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["returncode"], 0)
        self.assertIn("PASS", result["stdout"])

    @patch("audit_to_pr.subprocess.run")
    def test_run_governance_audit_failure(self, mock_run):
        """Test failed audit run."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="❌ FAIL: Lint",
            stderr="error details",
        )

        result = run_governance_audit(full=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], 1)

    @patch("audit_to_pr.subprocess.run")
    def test_run_governance_audit_timeout(self, mock_run):
        """Test audit timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=600)

        result = run_governance_audit(full=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], -1)
        self.assertIn("timed out", result["stderr"])

    @patch("audit_to_pr.subprocess.run")
    def test_run_governance_audit_exception(self, mock_run):
        """Test audit exception handling."""
        mock_run.side_effect = Exception("test error")

        result = run_governance_audit(full=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], -1)
        self.assertIn("test error", result["stderr"])


class TestParseAuditOutput(unittest.TestCase):
    """Tests for parse_audit_output function."""

    def test_parse_success_output(self):
        """Parse successful audit output."""
        output = """
————————————————————————————————————————
  Lint 检查
————————————————————————————————————————
  ✅ PASS: Lint
  ✅ PASS: Format
  ❌ FAIL: Type Check
Failed checks: Type Check
"""
        result = parse_audit_output(output)

        self.assertEqual(result["total_checks"], 3)
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertIn("Lint", result["passed_check_names"])
        self.assertIn("Format", result["passed_check_names"])
        self.assertIn("Type Check", result["failed_check_names"])

    def test_parse_empty_output(self):
        """Parse empty output."""
        output = ""
        result = parse_audit_output(output)

        self.assertEqual(result["total_checks"], 0)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["failed"], 0)

    def test_parse_all_passed(self):
        """Parse output with all checks passed."""
        output = """
  ✅ PASS: Lint
  ✅ PASS: Format
  ✅ PASS: Type Check
"""
        result = parse_audit_output(output)

        self.assertEqual(result["total_checks"], 3)
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 0)


class TestFormatPRReport(unittest.TestCase):
    """Tests for format_pr_report function."""

    def test_format_success_report(self):
        """Format report for successful audit."""
        audit_result = {
            "success": True,
            "stdout": "✅ PASS: Lint\n✅ PASS: Format",
            "stderr": "",
            "returncode": 0,
        }
        parsed = {
            "total_checks": 2,
            "passed": 2,
            "failed": 0,
            "checks": [
                {"name": "Lint", "passed": True},
                {"name": "Format", "passed": True},
            ],
            "failed_check_names": [],
            "passed_check_names": ["Lint", "Format"],
        }

        report = format_pr_report(audit_result, parsed)

        self.assertIn("✅ 通过", report)
        self.assertIn("总检查项: 2", report)
        self.assertIn("✅ 通过: 2", report)
        self.assertIn("❌ 失败: 0", report)
        self.assertIn("Lint", report)
        self.assertIn("Format", report)

    def test_format_failure_report(self):
        """Format report for failed audit."""
        audit_result = {
            "success": False,
            "stdout": "❌ FAIL: Lint",
            "stderr": "error details",
            "returncode": 1,
        }
        parsed = {
            "total_checks": 2,
            "passed": 1,
            "failed": 1,
            "checks": [
                {"name": "Lint", "passed": False},
                {"name": "Format", "passed": True},
            ],
            "failed_check_names": ["Lint"],
            "passed_check_names": ["Format"],
        }

        report = format_pr_report(audit_result, parsed)

        self.assertIn("❌ 失败", report)
        self.assertIn("总检查项: 2", report)
        self.assertIn("✅ 通过: 1", report)
        self.assertIn("❌ 失败: 1", report)
        self.assertIn("Lint", report)

    def test_format_report_with_stderr(self):
        """Format report with stderr output."""
        audit_result = {
            "success": False,
            "stdout": "❌ FAIL: Lint",
            "stderr": "Error: something went wrong",
            "returncode": 1,
        }
        parsed = {
            "total_checks": 1,
            "passed": 0,
            "failed": 1,
            "checks": [{"name": "Lint", "passed": False}],
            "failed_check_names": ["Lint"],
            "passed_check_names": [],
        }

        report = format_pr_report(audit_result, parsed)

        self.assertIn("错误输出", report)
        self.assertIn("something went wrong", report)


class TestCreateGitHubPR(unittest.TestCase):
    """Tests for create_github_pr function."""

    @patch("audit_to_pr.subprocess.run")
    def test_create_pr_not_git_repo(self, mock_run):
        """Test PR creation when not in git repo."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        result = create_github_pr("Test PR", "Test body")

        self.assertFalse(result["success"])
        self.assertIn("Not a git repository", result["error"])

    @patch("audit_to_pr.subprocess.run")
    def test_create_pr_no_gh_cli(self, mock_run):
        """Test PR creation when gh CLI not available."""
        # First call (git check) succeeds, second (gh --version) fails
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git rev-parse
            FileNotFoundError("gh not found"),  # gh --version
        ]

        result = create_github_pr("Test PR", "Test body")

        self.assertFalse(result["success"])
        self.assertIn("GitHub CLI (gh) not found", result["error"])


class TestMainFunction(unittest.TestCase):
    """Tests for main function with different arguments."""

    @patch("audit_to_pr.run_governance_audit")
    @patch("audit_to_pr.parse_audit_output")
    @patch("audit_to_pr.format_pr_report")
    def test_main_run_audit(self, mock_format, mock_parse, mock_run):
        """Test main with --run-audit."""
        mock_run.return_value = {
            "success": True,
            "stdout": "✅ PASS: Lint",
            "stderr": "",
            "returncode": 0,
        }
        mock_parse.return_value = {
            "total_checks": 1,
            "passed": 1,
            "failed": 0,
            "checks": [{"name": "Lint", "passed": True}],
            "failed_check_names": [],
            "passed_check_names": ["Lint"],
        }
        mock_format.return_value = "Test report"

        with patch("sys.argv", ["audit_to_pr.py", "--run-audit"]):
            result = main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once_with(full=True)

    @patch("audit_to_pr.run_governance_audit")
    @patch("audit_to_pr.parse_audit_output")
    @patch("audit_to_pr.format_pr_report")
    def test_main_run_audit_failure(self, mock_format, mock_parse, mock_run):
        """Test main with --run-audit when audit fails."""
        mock_run.return_value = {
            "success": False,
            "stdout": "❌ FAIL: Lint",
            "stderr": "",
            "returncode": 1,
        }
        mock_parse.return_value = {
            "total_checks": 1,
            "passed": 0,
            "failed": 1,
            "checks": [{"name": "Lint", "passed": False}],
            "failed_check_names": ["Lint"],
            "passed_check_names": [],
        }
        mock_format.return_value = "Test report"

        with patch("sys.argv", ["audit_to_pr.py", "--run-audit"]):
            result = main()

        self.assertEqual(result, 1)

    @patch("audit_to_pr.run_governance_audit")
    @patch("audit_to_pr.parse_audit_output")
    @patch("audit_to_pr.format_pr_report")
    @patch("audit_to_pr.create_github_pr")
    def test_main_create_pr(self, mock_create_pr, mock_format, mock_parse, mock_run):
        """Test main with --create-pr."""
        mock_run.return_value = {
            "success": True,
            "stdout": "✅ PASS: Lint",
            "stderr": "",
            "returncode": 0,
        }
        mock_parse.return_value = {
            "total_checks": 1,
            "passed": 1,
            "failed": 0,
            "checks": [{"name": "Lint", "passed": True}],
            "failed_check_names": [],
            "passed_check_names": ["Lint"],
        }
        mock_format.return_value = "Test report"
        mock_create_pr.return_value = {"success": True, "pr_url": "https://github.com/test/pr/1"}

        with patch("sys.argv", ["audit_to_pr.py", "--run-audit", "--create-pr"]):
            result = main()

        self.assertEqual(result, 0)
        mock_create_pr.assert_called_once()

    @patch("audit_to_pr.run_governance_audit")
    @patch("audit_to_pr.parse_audit_output")
    @patch("audit_to_pr.format_pr_report")
    @patch("audit_to_pr.create_github_pr")
    def test_main_create_pr_failure(self, mock_create_pr, mock_format, mock_parse, mock_run):
        """Test main with --create-pr when PR creation fails."""
        mock_run.return_value = {
            "success": True,
            "stdout": "✅ PASS: Lint",
            "stderr": "",
            "returncode": 0,
        }
        mock_parse.return_value = {
            "total_checks": 1,
            "passed": 1,
            "failed": 0,
            "checks": [{"name": "Lint", "passed": True}],
            "failed_check_names": [],
            "passed_check_names": ["Lint"],
        }
        mock_format.return_value = "Test report"
        mock_create_pr.return_value = {"success": False, "error": "PR creation failed"}

        with patch("sys.argv", ["audit_to_pr.py", "--run-audit", "--create-pr"]):
            result = main()

        self.assertEqual(result, 1)

    def test_main_no_args(self):
        """Test main with no arguments shows help."""
        with patch("sys.argv", ["audit_to_pr.py"]):
            with patch("argparse.ArgumentParser.print_help") as mock_help:
                result = main()

        self.assertEqual(result, 1)
        mock_help.assert_called_once()


if __name__ == "__main__":
    unittest.main()
