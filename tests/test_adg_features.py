"""Tests for ADG CLI new features (incremental check, SARIF, rule authoring, trend, notify)."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.adg_cli import (
    Issue,
    _format_sarif,
    _format_trend_report,
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
    _load_trend_data,
    _record_trend,
    _save_trend_data,
    _send_dingtalk_notification,
    _send_slack_notification,
    _test_rule,
    _validate_rule,
    cmd_trend,
)

# ──────────────────────────────────────────────────────────
# SARIF Output Tests
# ──────────────────────────────────────────────────────────


class TestSarifOutput:
    """Test SARIF format output."""

    def test_sarif_empty_issues(self):
        """SARIF output with no issues."""
        result = _format_sarif([], "python", None)
        data = json.loads(result)
        assert data["version"] == "2.1.0"
        assert len(data["runs"]) == 1
        assert data["runs"][0]["results"] == []

    def test_sarif_with_issues(self):
        """SARIF output with issues."""
        issues = [
            Issue(
                rule_id="py-bare-except",
                severity="error",
                category="code_quality",
                file="/test.py",
                line=10,
                column=1,
                message="Avoid bare except",
                fix_hint="Use except Exception:",
            )
        ]
        result = _format_sarif(issues, "python", None)
        data = json.loads(result)

        assert len(data["runs"][0]["results"]) == 1
        assert data["runs"][0]["results"][0]["ruleId"] == "py-bare-except"
        assert data["runs"][0]["results"][0]["level"] == "error"

    def test_sarif_severity_mapping(self):
        """SARIF maps severity correctly."""
        issues = [
            Issue("r1", "error", "security", "/a.py", 1, 1, "err", ""),
            Issue("r2", "warning", "code_quality", "/a.py", 2, 1, "warn", ""),
            Issue("r3", "info", "code_quality", "/a.py", 3, 1, "info", ""),
        ]
        result = _format_sarif(issues, "python", None)
        data = json.loads(result)

        levels = [r["level"] for r in data["runs"][0]["results"]]
        assert levels == ["error", "warning", "note"]

    def test_sarif_rules_collected(self):
        """SARIF collects unique rules."""
        issues = [
            Issue("py-r1", "error", "security", "/a.py", 1, 1, "msg1", ""),
            Issue("py-r1", "error", "security", "/a.py", 2, 1, "msg1", ""),
            Issue("py-r2", "warning", "code_quality", "/a.py", 3, 1, "msg2", ""),
        ]
        result = _format_sarif(issues, "python", None)
        data = json.loads(result)

        rules = data["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 2


# ──────────────────────────────────────────────────────────
# Incremental Check Tests
# ──────────────────────────────────────────────────────────


class TestIncrementalCheck:
    """Test git-based incremental checking."""

    @patch("subprocess.run")
    def test_get_git_changed_files(self, mock_run):
        """Get files changed since a git ref."""
        mock_run.return_value = MagicMock(returncode=0, stdout="file1.py\nfile2.py\n", stderr="")

        with patch("pathlib.Path.is_file", return_value=True):
            files = _get_git_changed_files("HEAD~1")

        assert len(files) == 2
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_git_changed_files_error(self, mock_run):
        """Handle git command error."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="not a git repo")

        files = _get_git_changed_files("HEAD~1")
        assert files == []

    @patch("subprocess.run")
    def test_get_staged_files(self, mock_run):
        """Get staged files."""
        mock_run.return_value = MagicMock(returncode=0, stdout="staged.py\n", stderr="")

        with patch("pathlib.Path.is_file", return_value=True):
            files = _get_staged_files()

        assert len(files) == 1

    @patch("subprocess.run")
    def test_get_unstaged_files(self, mock_run):
        """Get unstaged files."""
        mock_run.return_value = MagicMock(returncode=0, stdout="unstaged.py\n", stderr="")

        with patch("pathlib.Path.is_file", return_value=True):
            files = _get_unstaged_files()

        assert len(files) == 1


# ──────────────────────────────────────────────────────────
# Rule Authoring Tests
# ──────────────────────────────────────────────────────────


class TestRuleAuthoring:
    """Test rule authoring tools."""

    def test_validate_rule_valid(self):
        """Validate a valid rule."""
        rule = {
            "id": "test-rule",
            "severity": "warning",
            "category": "code_quality",
            "pattern": r"test.*pattern",
            "message": "Test message",
        }
        errors = _validate_rule(rule)
        assert errors == []

    def test_validate_rule_missing_fields(self):
        """Validate rule with missing fields."""
        rule = {"id": "test"}
        errors = _validate_rule(rule)
        assert len(errors) >= 3  # severity, category, pattern, message

    def test_validate_rule_invalid_severity(self):
        """Validate rule with invalid severity."""
        rule = {
            "id": "test",
            "severity": "critical",  # invalid
            "category": "code_quality",
            "pattern": r"test",
            "message": "msg",
        }
        errors = _validate_rule(rule)
        assert any("severity" in e for e in errors)

    def test_validate_rule_invalid_regex(self):
        """Validate rule with invalid regex."""
        rule = {
            "id": "test",
            "severity": "warning",
            "category": "code_quality",
            "pattern": "[invalid",  # unclosed bracket
            "message": "msg",
        }
        errors = _validate_rule(rule)
        assert any("regex" in e for e in errors)

    def test_test_rule(self):
        """Test a rule against files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello')\n")
            f.write("x = None\n")
            test_file = Path(f.name)

        rule = {
            "id": "test-print",
            "pattern": r"\bprint\(",
            "message": "Use logging",
        }

        results = _test_rule(rule, [test_file])
        assert results["files_tested"] == 1
        assert len(results["matches"]) == 1

        test_file.unlink()

    def test_test_rule_no_matches(self):
        """Test a rule with no matches."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            test_file = Path(f.name)

        rule = {
            "id": "test",
            "pattern": r"\bprint\(",
            "message": "msg",
        }

        results = _test_rule(rule, [test_file])
        assert len(results["matches"]) == 0

        test_file.unlink()


# ──────────────────────────────────────────────────────────
# Trend Dashboard Tests
# ──────────────────────────────────────────────────────────


class TestTrendDashboard:
    """Test trend tracking and dashboard."""

    def test_save_and_load_trend_data(self, tmp_path):
        """Save and load trend data."""
        data = [
            {"timestamp": "2024-01-01T00:00:00", "errors": 5, "warnings": 10, "info": 3},
            {"timestamp": "2024-01-02T00:00:00", "errors": 3, "warnings": 8, "info": 2},
        ]

        _save_trend_data(tmp_path, data)
        loaded = _load_trend_data(tmp_path)

        assert loaded == data

    def test_load_nonexistent_trend_data(self, tmp_path):
        """Load trend data when file doesn't exist."""
        loaded = _load_trend_data(tmp_path)
        assert loaded == []

    def test_record_trend(self, tmp_path):
        """Record a trend data point."""
        issues = [
            Issue("r1", "error", "security", "/a.py", 1, 1, "err", ""),
            Issue("r2", "warning", "code_quality", "/a.py", 2, 1, "warn", ""),
        ]

        data_point = _record_trend(tmp_path, issues, "python")

        assert data_point["errors"] == 1
        assert data_point["warnings"] == 1
        assert data_point["info"] == 0

        # Check saved
        loaded = _load_trend_data(tmp_path)
        assert len(loaded) == 1

    def test_format_trend_report_empty(self):
        """Format empty trend data."""
        result = _format_trend_report([])
        assert "No trend data" in result

    def test_format_trend_report_with_data(self):
        """Format trend data."""
        data = [
            {"timestamp": "2024-01-01T00:00:00", "errors": 5, "warnings": 10, "info": 3},
            {"timestamp": "2024-01-02T00:00:00", "errors": 3, "warnings": 8, "info": 2},
        ]

        result = _format_trend_report(data)
        assert "Errors" in result
        assert "Warnings" in result

    def test_format_trend_report_json(self):
        """Format trend data as JSON."""
        data = [{"timestamp": "2024-01-01", "errors": 5}]
        result = _format_trend_report(data, output_json=True)
        parsed = json.loads(result)
        assert parsed == data

    def test_trend_data_limit(self, tmp_path):
        """Trend data is limited to 100 entries."""
        data = [{"timestamp": f"2024-01-{i:02d}", "errors": i} for i in range(150)]

        # Save more than 100 entries
        _save_trend_data(tmp_path, data)

        # Record one more to trigger limit
        _record_trend(tmp_path, [], "python")

        loaded = _load_trend_data(tmp_path)
        assert len(loaded) <= 100


# ──────────────────────────────────────────────────────────
# Webhook Notification Tests
# ──────────────────────────────────────────────────────────


class TestWebhookNotification:
    """Test webhook notifications."""

    def test_slack_notification_format(self):
        """Slack notification sends correct format."""
        issues = [
            Issue("r1", "error", "security", "/a.py", 1, 1, "err", ""),
        ]

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            result = _send_slack_notification("https://hooks.slack.com/test", issues, "python", "test-project")

        assert result is True
        mock_open.assert_called_once()

    def test_dingtalk_notification_format(self):
        """DingTalk notification sends correct format."""
        issues = [
            Issue("r1", "warning", "code_quality", "/a.py", 1, 1, "warn", ""),
        ]

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            result = _send_dingtalk_notification("https://oapi.dingtalk.com/test", issues, "python", "test-project")

        assert result is True

    def test_slack_notification_error(self):
        """Slack notification handles errors."""
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            result = _send_slack_notification("https://hooks.slack.com/test", [], "python", "test")

        assert result is False


# ──────────────────────────────────────────────────────────
# CLI Command Tests
# ──────────────────────────────────────────────────────────


class TestTrendCommand:
    """Test trend command."""

    def test_trend_empty(self, tmp_path):
        """Trend command with no data."""
        args = argparse.Namespace(path=str(tmp_path), json=False, clear=False)
        result = cmd_trend(args)
        assert result == 0

    def test_trend_clear(self, tmp_path):
        """Trend command clear flag."""
        # Create trend file
        trend_file = tmp_path / ".adg" / "trend.json"
        trend_file.parent.mkdir(parents=True)
        trend_file.write_text("[]")

        args = argparse.Namespace(path=str(tmp_path), json=False, clear=True)
        result = cmd_trend(args)
        assert result == 0
        assert not trend_file.exists()


# ──────────────────────────────────────────────────────────
# Extended Auto-fix Tests
# ──────────────────────────────────────────────────────────


class TestExtendedAutoFix:
    """Test extended auto-fix rules."""

    def test_go_println_fix(self, tmp_path):
        """Go println fix."""
        from tools.scripts.adg_cli import FIX_RULES

        assert "go-println" in FIX_RULES
        assert FIX_RULES["go-println"]["replacement"] == "log.Println("

    def test_rust_unwrap_fix(self, tmp_path):
        """Rust unwrap fix."""
        from tools.scripts.adg_cli import FIX_RULES

        assert "rust-unwrap-question" in FIX_RULES
        assert FIX_RULES["rust-unwrap-question"]["replacement"] == ".unwrap_or_default()"

    def test_rust_panic_fix(self, tmp_path):
        """Rust panic fix."""
        from tools.scripts.adg_cli import FIX_RULES

        assert "rust-panic-macro" in FIX_RULES
        assert FIX_RULES["rust-panic-macro"]["replacement"] == "return Err("
