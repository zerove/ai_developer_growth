"""Tests for src/cli/commands/audit.py — text/json output, strict mode, overridden violations."""

from unittest.mock import MagicMock, patch

from src.cli.commands.audit import audit


def _make_violation(rule_id="R001", severity="Warning", message="Missing docstring"):
    """Create a mock violation matching the attributes audit.py reads."""
    v = MagicMock()
    v.rule_id = rule_id
    v.severity = severity
    v.message = message
    v.to_dict.return_value = {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
    }
    return v


class TestAuditCommand:
    """Tests for the audit CLI command."""

    @patch("src.cli.commands.audit.typer")
    @patch("src.cli.commands.audit.AIContextSync")
    def test_audit_no_changes(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""
        mock_sync.analyzer.get_last_commit_message.return_value = ""
        mock_sync.analyzer.filter_diff.return_value = ""

        audit(config=".ai-sync.json", strict=False, format="text")

        mock_typer.echo.assert_called_once()
        assert "No changes to audit" in mock_typer.echo.call_args[0][0]

    @patch("src.cli.commands.audit.typer")
    @patch("src.cli.commands.audit.AIContextSync")
    def test_audit_text_output(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = (
            "diff --git a/src/main.py\n"
        )
        mock_sync.analyzer.get_last_commit_message.return_value = "chore: update"
        mock_sync.analyzer.filter_diff.return_value = "diff --git a/src/main.py\n"
        mock_sync.feedback.history = []

        violation = _make_violation(rule_id="R001", severity="Warning")
        mock_sync.auditor.audit.return_value = [violation]

        audit(config=".ai-sync.json", strict=False, format="text")

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("R001" in c for c in calls)

    @patch("src.cli.commands.audit.typer")
    @patch("src.cli.commands.audit.AIContextSync")
    def test_audit_json_output(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff\n"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "diff"
        mock_sync.feedback.history = []

        violation = _make_violation()
        mock_sync.auditor.audit.return_value = [violation]

        audit(config=".ai-sync.json", strict=False, format="json")

        mock_typer.echo.assert_called_once()
        output = mock_typer.echo.call_args[0][0]
        assert "R001" in output

    @patch("src.cli.commands.audit.typer")
    @patch("src.cli.commands.audit.AIContextSync")
    def test_audit_strict_critical(self, mock_sync_cls, mock_typer):
        import typer as _typer

        mock_typer.Exit = _typer.Exit  # real Exit class so `raise` works

        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff\n"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "diff"
        mock_sync.feedback.history = []

        violation = _make_violation(severity="Critical", message="Security issue")
        mock_sync.auditor.audit.return_value = [violation]

        try:
            audit(config=".ai-sync.json", strict=True, format="text")
        except Exception:
            pass  # typer.Exit propagates through cli_error_handler

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("STRICT" in c.upper() for c in calls)

    @patch("src.cli.commands.audit.typer")
    @patch("src.cli.commands.audit.AIContextSync")
    def test_audit_strict_no_critical(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff\n"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "diff"
        mock_sync.feedback.history = []

        violation = _make_violation(severity="Warning", message="Minor issue")
        mock_sync.auditor.audit.return_value = [violation]

        audit(config=".ai-sync.json", strict=True, format="text")

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("Warning" in c for c in calls)

    @patch("src.cli.commands.audit.typer")
    @patch("src.cli.commands.audit.AIContextSync")
    def test_audit_overridden_violations(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff\n"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "diff"

        mock_sync.feedback.history = [{"rule_id": "R001", "status": "overridden"}]

        violation = _make_violation(rule_id="R001")
        mock_sync.auditor.audit.return_value = [violation]

        audit(config=".ai-sync.json", strict=False, format="text")

        mock_typer.echo.assert_called_once()
        assert "comply" in mock_typer.echo.call_args[0][0].lower()
