"""Tests for src/cli/commands/monitoring.py — _validate_file_path, watch, apply_fix."""
from unittest.mock import MagicMock, mock_open, patch

from src.cli.commands.monitoring import _validate_file_path, apply_fix, watch


class TestValidateFilePath:
    """Tests for the _validate_file_path helper."""

    def test_valid_relative_path(self):
        assert _validate_file_path("src/main.py") is True

    def test_valid_simple_filename(self):
        assert _validate_file_path("README.md") is True

    def test_rejects_absolute_path(self):
        assert _validate_file_path("/etc/passwd") is False

    def test_rejects_parent_traversal(self):
        assert _validate_file_path("../../etc/passwd") is False

    def test_rejects_tilde_prefix(self):
        assert _validate_file_path("~/.ssh/id_rsa") is False

    def test_rejects_empty_string(self):
        assert _validate_file_path("") is False

    def test_rejects_whitespace_only(self):
        assert _validate_file_path("   ") is False

    def test_rejects_none_like(self):
        assert _validate_file_path("") is False


class TestWatchCommand:
    """Tests for the watch CLI command."""

    @patch("src.cli.commands.monitoring.WatchManager")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_watch_starts_watcher(self, mock_sync_cls, mock_watcher_cls):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_watcher = MagicMock()
        mock_watcher_cls.return_value = mock_watcher

        watch(config=".ai-sync.json", path=".")

        mock_sync_cls.assert_called_once_with(config_path=".ai-sync.json")
        mock_watcher_cls.assert_called_once_with(mock_sync)
        mock_watcher.start.assert_called_once_with(path=".")


class TestApplyFixCommand:
    """Tests for the apply-fix CLI command."""

    @patch("src.cli.commands.monitoring.typer")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_apply_fix_unknown_file(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""

        apply_fix(rule_id="R001", config=".ai-sync.json", dry_run=False)

        mock_typer.echo.assert_called_once()
        assert "Could not identify the target file" in mock_typer.echo.call_args[0][0]

    @patch("src.cli.commands.monitoring.typer")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_apply_fix_unsafe_path(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "+++ b/../../etc/passwd\n"

        apply_fix(rule_id="R001", config=".ai-sync.json", dry_run=False)

        mock_typer.echo.assert_called_once()
        assert "Rejected unsafe file path" in mock_typer.echo.call_args[0][0]

    @patch("src.cli.commands.monitoring.typer")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_apply_fix_no_violation(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "+++ b/src/main.py\n"
        mock_sync.auditor.audit.return_value = []

        apply_fix(rule_id="R001", config=".ai-sync.json", dry_run=False)

        mock_typer.echo.assert_called_once()
        assert "No active violation found" in mock_typer.echo.call_args[0][0]

    @patch("src.cli.commands.monitoring.typer")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_apply_fix_dry_run(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "+++ b/src/main.py\n"

        violation = MagicMock()
        violation.rule_id = "R001"
        mock_sync.auditor.audit.return_value = [violation]
        mock_sync.auditor.get_relevant_specs.return_value = "spec content"
        mock_sync.auditor.generate_fix.return_value = "fixed code"

        apply_fix(rule_id="R001", config=".ai-sync.json", dry_run=True)

        # Should echo dry-run preview, not write file
        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("Dry-run" in c for c in calls)

    @patch("src.cli.commands.monitoring.typer")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_apply_fix_writes_file(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "+++ b/src/main.py\n"

        violation = MagicMock()
        violation.rule_id = "R001"
        mock_sync.auditor.audit.return_value = [violation]
        mock_sync.auditor.get_relevant_specs.return_value = "spec"
        mock_sync.auditor.generate_fix.return_value = "fixed code"

        with patch("builtins.open", mock_open()) as mock_file:
            apply_fix(rule_id="R001", config=".ai-sync.json", dry_run=False)

        mock_file.assert_called_once()
        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("Successfully applied" in c for c in calls)

    @patch("src.cli.commands.monitoring.typer")
    @patch("src.cli.commands.monitoring.AIContextSync")
    def test_apply_fix_os_error(self, mock_sync_cls, mock_typer):
        import typer as _typer
        mock_typer.Exit = _typer.Exit  # real Exit class so `raise` works

        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "+++ b/src/main.py\n"

        violation = MagicMock()
        violation.rule_id = "R001"
        mock_sync.auditor.audit.return_value = [violation]
        mock_sync.auditor.get_relevant_specs.return_value = "spec"
        mock_sync.auditor.generate_fix.return_value = "fixed code"

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            try:
                apply_fix(rule_id="R001", config=".ai-sync.json", dry_run=False)
            except Exception:
                pass  # typer.Exit propagates through cli_error_handler

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("Failed to write" in c for c in calls)
