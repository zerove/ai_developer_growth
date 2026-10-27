# 拆分自 tests/test_audit_to_pr.py

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from tools.scripts.audit_to_pr import (
    create_github_pr,
    format_pr_report,
    main,
)


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

    @patch("tools.scripts.audit_to_pr.subprocess.run")
    def test_create_pr_not_git_repo(self, mock_run):
        """Test PR creation when not in git repo."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        result = create_github_pr("Test PR", "Test body")

        self.assertFalse(result["success"])
        self.assertIn("Not a git repository", result["error"])

    @patch("tools.scripts.audit_to_pr.subprocess.run")
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

    @patch("tools.scripts.audit_to_pr.run_governance_audit")
    @patch("tools.scripts.audit_to_pr.parse_audit_output")
    @patch("tools.scripts.audit_to_pr.format_pr_report")
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

    @patch("tools.scripts.audit_to_pr.run_governance_audit")
    @patch("tools.scripts.audit_to_pr.parse_audit_output")
    @patch("tools.scripts.audit_to_pr.format_pr_report")
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

    @patch("tools.scripts.audit_to_pr.run_governance_audit")
    @patch("tools.scripts.audit_to_pr.parse_audit_output")
    @patch("tools.scripts.audit_to_pr.format_pr_report")
    @patch("tools.scripts.audit_to_pr.create_github_pr")
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
        mock_create_pr.return_value = {
            "success": True,
            "pr_url": "https://github.com/test/pr/1",
        }

        with patch("sys.argv", ["audit_to_pr.py", "--run-audit", "--create-pr"]):
            result = main()

        self.assertEqual(result, 0)
        mock_create_pr.assert_called_once()

    @patch("tools.scripts.audit_to_pr.run_governance_audit")
    @patch("tools.scripts.audit_to_pr.parse_audit_output")
    @patch("tools.scripts.audit_to_pr.format_pr_report")
    @patch("tools.scripts.audit_to_pr.create_github_pr")
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
