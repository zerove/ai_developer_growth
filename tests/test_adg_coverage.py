"""Additional tests for ADG CLI to improve coverage."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from tools.scripts.adg_cli import (
    _create_rule_interactive,
    _test_rule,
    _validate_rule,
    cmd_rule,
    cmd_trend,
    cmd_notify,
    _format_trend_report,
    _load_trend_data,
    _save_trend_data,
    _record_trend,
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
    _send_slack_notification,
    _send_dingtalk_notification,
    _format_sarif,
    Issue,
    load_rules_for_language,
)
import argparse


class TestCreateRuleInteractive:
    """Test interactive rule creation."""

    def test_create_rule_success(self):
        """Interactive rule creation succeeds."""
        inputs = [
            "test-rule",        # rule_id
            "python",           # language
            "code_quality",     # category
            "warning",          # severity
            r"test\(\)",       # pattern
            "Test message",     # message
            "Fix this",         # fix_hint
        ]
        
        with patch("builtins.input", side_effect=inputs):
            rule = _create_rule_interactive()
        
        assert rule["id"] == "test-rule"
        assert rule["language"] == "python"
        assert rule["category"] == "code_quality"
        assert rule["severity"] == "warning"
        assert rule["pattern"] == r"test\(\)"
        assert rule["message"] == "Test message"
        assert rule["fix_hint"] == "Fix this"

    def test_create_rule_cancelled(self):
        """Interactive rule creation cancelled."""
        with patch("builtins.input", return_value=""):
            rule = _create_rule_interactive()
        
        assert rule == {}

    def test_create_rule_defaults(self):
        """Interactive rule creation uses defaults."""
        inputs = [
            "test-rule",        # rule_id
            "python",           # language
            "",                 # category (empty = default)
            "",                 # severity (empty = default)
            r"test\(\)",       # pattern
            "Test message",     # message
            "",                 # fix_hint
        ]
        
        with patch("builtins.input", side_effect=inputs):
            rule = _create_rule_interactive()
        
        assert rule["category"] == "code_quality"
        assert rule["severity"] == "warning"


class TestCmdRule:
    """Test rule command handler."""

    def test_rule_no_subcommand(self):
        """Rule command with no subcommand."""
        args = argparse.Namespace(rule_command=None)
        result = cmd_rule(args)
        assert result == 1

    def test_rule_create_with_output(self, tmp_path):
        """Rule create with output file."""
        output_file = tmp_path / "test_rule.yaml"
        inputs = [
            "test-rule",        # rule_id
            "python",           # language
            "code_quality",     # category
            "warning",          # severity
            r"test_pattern",    # pattern (simple pattern)
            "Test message",     # message
            "Fix this",         # fix_hint
        ]
        
        with patch("builtins.input", side_effect=inputs):
            args = argparse.Namespace(rule_command="create", output=str(output_file))
            result = cmd_rule(args)
        
        assert result == 0
        assert output_file.exists()

    def test_rule_validate_valid(self, tmp_path):
        """Rule validate with valid rule."""
        rule_file = tmp_path / "valid_rule.yaml"
        rule_file.write_text("""
id: test-rule
severity: warning
category: code_quality
pattern: "test_pattern"
message: "Test message"
""")
        
        args = argparse.Namespace(rule_command="validate", rule_file=str(rule_file))
        result = cmd_rule(args)
        assert result == 0

    def test_rule_validate_invalid(self, tmp_path):
        """Rule validate with invalid rule."""
        rule_file = tmp_path / "invalid_rule.yaml"
        rule_file.write_text("""
id: test-rule
severity: invalid
""")
        
        args = argparse.Namespace(rule_command="validate", rule_file=str(rule_file))
        result = cmd_rule(args)
        assert result == 1

    def test_rule_validate_nonexistent(self):
        """Rule validate with nonexistent file."""
        args = argparse.Namespace(rule_command="validate", rule_file="/nonexistent.yaml")
        result = cmd_rule(args)
        assert result == 1

    def test_rule_test_with_file(self, tmp_path):
        """Rule test with a test file."""
        rule_file = tmp_path / "test_rule.yaml"
        rule_file.write_text("""
pattern: "print_pattern"
message: "Use logging"
""")
        
        test_file = tmp_path / "test.py"
        test_file.write_text("print_pattern('hello')\n")
        
        args = argparse.Namespace(rule_command="test", rule_file=str(rule_file), path=str(tmp_path))
        result = cmd_rule(args)
        assert result == 0

    def test_rule_test_no_matches(self, tmp_path):
        """Rule test with no matches."""
        rule_file = tmp_path / "test_rule.yaml"
        rule_file.write_text("""
pattern: "nonexistent_pattern"
message: "Test"
""")
        
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        
        args = argparse.Namespace(rule_command="test", rule_file=str(rule_file), path=str(tmp_path))
        result = cmd_rule(args)
        assert result == 0


class TestCmdTrend:
    """Test trend command handler."""

    def test_trend_empty(self, tmp_path):
        """Trend with no data."""
        args = argparse.Namespace(path=str(tmp_path), json=False, clear=False)
        result = cmd_trend(args)
        assert result == 0

    def test_trend_with_data(self, tmp_path):
        """Trend with existing data."""
        data = [
            {"timestamp": "2024-01-01T00:00:00", "errors": 5, "warnings": 10, "info": 3, "total": 18, "files_checked": 5, "language": "python"},
        ]
        _save_trend_data(tmp_path, data)
        
        args = argparse.Namespace(path=str(tmp_path), json=False, clear=False)
        result = cmd_trend(args)
        assert result == 0

    def test_trend_json_output(self, tmp_path):
        """Trend JSON output."""
        data = [{"timestamp": "2024-01-01", "errors": 5}]
        _save_trend_data(tmp_path, data)
        
        args = argparse.Namespace(path=str(tmp_path), json=True, clear=False)
        result = cmd_trend(args)
        assert result == 0

    def test_trend_clear_existing(self, tmp_path):
        """Trend clear with existing data."""
        trend_file = tmp_path / ".adg" / "trend.json"
        trend_file.parent.mkdir(parents=True)
        trend_file.write_text("[]")
        
        args = argparse.Namespace(path=str(tmp_path), json=False, clear=True)
        result = cmd_trend(args)
        assert result == 0
        assert not trend_file.exists()

    def test_trend_clear_nonexistent(self, tmp_path):
        """Trend clear with no data."""
        args = argparse.Namespace(path=str(tmp_path), json=False, clear=True)
        result = cmd_trend(args)
        assert result == 0


class TestCmdNotify:
    """Test notify command handler."""

    def test_notify_slack(self, tmp_path):
        """Notify with Slack webhook."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")
        
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            args = argparse.Namespace(
                path=str(test_file),
                webhook="slack://test-token",
                lang="python",
                project="test-project"
            )
            result = cmd_notify(args)
        
        assert result == 0

    def test_notify_dingtalk(self, tmp_path):
        """Notify with DingTalk webhook."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")
        
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            args = argparse.Namespace(
                path=str(test_file),
                webhook="dingtalk://test-token",
                lang="python",
                project="test-project"
            )
            result = cmd_notify(args)
        
        assert result == 0

    def test_notify_unknown_scheme(self, tmp_path):
        """Notify with unknown webhook scheme."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")
        
        args = argparse.Namespace(
            path=str(test_file),
            webhook="unknown://test",
            lang="python",
            project="test"
        )
        result = cmd_notify(args)
        assert result == 1


class TestGitFunctions:
    """Test git integration functions."""

    @patch("subprocess.run")
    def test_git_changed_files_timeout(self, mock_run):
        """Handle git timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
        
        files = _get_git_changed_files("HEAD~1")
        assert files == []

    @patch("subprocess.run")
    def test_git_changed_files_not_found(self, mock_run):
        """Handle git not found."""
        mock_run.side_effect = FileNotFoundError()
        
        files = _get_git_changed_files("HEAD~1")
        assert files == []

    @patch("subprocess.run")
    def test_git_changed_files_empty_output(self, mock_run):
        """Handle empty git output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        files = _get_git_changed_files("HEAD~1")
        assert files == []


class TestWebhookErrors:
    """Test webhook error handling."""

    def test_slack_notification_exception(self):
        """Slack notification handles exceptions."""
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            result = _send_slack_notification("https://test", [], "python", "test")
            assert result is False

    def test_dingtalk_notification_exception(self):
        """DingTalk notification handles exceptions."""
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            result = _send_dingtalk_notification("https://test", [], "python", "test")
            assert result is False


class TestSarifExtended:
    """Test SARIF format with fix hints."""

    def test_sarif_with_fixes(self):
        """SARIF includes fix hints."""
        issues = [
            Issue("r1", "error", "security", "/a.py", 10, 5, "Error msg", "Fix hint")
        ]
        result = _format_sarif(issues, "python", None)
        data = json.loads(result)
        
        assert "fixes" in data["runs"][0]["results"][0]
        assert len(data["runs"][0]["results"][0]["fixes"]) == 1

    def test_sarif_without_fixes(self):
        """SARIF without fix hints."""
        issues = [
            Issue("r1", "error", "security", "/a.py", 10, 5, "Error msg", "")
        ]
        result = _format_sarif(issues, "python", None)
        data = json.loads(result)
        
        assert data["runs"][0]["results"][0]["fixes"] == []


class TestRuleValidationExtended:
    """Extended rule validation tests."""

    def test_validate_rule_all_severities(self):
        """All valid severities pass."""
        for severity in ["error", "warning", "info"]:
            rule = {
                "id": "test",
                "severity": severity,
                "category": "code_quality",
                "pattern": "test",
                "message": "msg",
            }
            errors = _validate_rule(rule)
            assert errors == [], f"Failed for severity {severity}"

    def test_validate_rule_all_categories(self):
        """All valid categories pass."""
        for category in ["security", "code_quality", "performance", "maintainability"]:
            rule = {
                "id": "test",
                "severity": "warning",
                "category": category,
                "pattern": "test",
                "message": "msg",
            }
            errors = _validate_rule(rule)
            assert errors == [], f"Failed for category {category}"


class TestTestRuleExtended:
    """Extended rule testing."""

    def test_test_rule_multiple_files(self, tmp_path):
        """Test rule against multiple files."""
        file1 = tmp_path / "a.py"
        file1.write_text("print('a')\nprint('b')\n")
        
        file2 = tmp_path / "b.py"
        file2.write_text("x = 1\n")
        
        rule = {"pattern": r"\bprint\(", "message": "msg"}
        results = _test_rule(rule, [file1, file2])
        
        assert results["files_tested"] == 2
        assert len(results["matches"]) == 2

    def test_test_rule_invalid_regex(self):
        """Test rule with invalid regex."""
        rule = {"pattern": "[invalid", "message": "msg"}
        results = _test_rule(rule, [])
        
        assert len(results["errors"]) == 1
        assert "Invalid pattern" in results["errors"][0]


class TestTrendExtended:
    """Extended trend tests."""

    def test_trend_report_with_trend(self):
        """Trend report shows trend direction."""
        data = [
            {"timestamp": "2024-01-01T00:00:00", "errors": 10, "warnings": 20, "info": 5, "total": 35, "files_checked": 10, "language": "python"},
            {"timestamp": "2024-01-02T00:00:00", "errors": 5, "warnings": 15, "info": 3, "total": 23, "files_checked": 10, "language": "python"},
        ]
        
        report = _format_trend_report(data)
        assert "↓" in report or "Errors" in report
