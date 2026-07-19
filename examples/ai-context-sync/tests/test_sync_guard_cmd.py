"""Tests for src/cli/commands/sync_guard.py — sync (normal, dry-run, detach) and guard."""
from unittest.mock import MagicMock, patch, call

from src.cli.commands.sync_guard import sync, guard


class TestSyncCommand:
    """Tests for the sync CLI command."""

    @patch("src.cli.commands.sync_guard.AIContextSync")
    @patch("src.cli.commands.sync_guard.typer")
    def test_sync_normal(self, mock_typer, mock_sync_cls):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync

        sync(config=".ai-sync.json", dry_run=False, detach=False)

        mock_sync_cls.assert_called_once_with(config_path=".ai-sync.json", dry_run=False)
        mock_sync.sync.assert_called_once()

    @patch("src.cli.commands.sync_guard.AIContextSync")
    @patch("src.cli.commands.sync_guard.typer")
    def test_sync_dry_run(self, mock_typer, mock_sync_cls):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync

        sync(config=".ai-sync.json", dry_run=True, detach=False)

        mock_sync_cls.assert_called_once_with(config_path=".ai-sync.json", dry_run=True)
        mock_sync.sync.assert_called_once()

    @patch("src.cli.commands.sync_guard.subprocess.Popen")
    @patch("src.cli.commands.sync_guard.typer")
    def test_sync_detach(self, mock_typer, mock_popen):
        sync(config=".ai-sync.json", dry_run=False, detach=True)

        mock_popen.assert_called_once()
        assert mock_popen.call_args[1].get("start_new_session") is True
        mock_typer.echo.assert_called_once()
        assert "background" in mock_typer.echo.call_args[0][0].lower()

    @patch("src.cli.commands.sync_guard.subprocess.Popen")
    @patch("src.cli.commands.sync_guard.typer")
    def test_sync_detach_dry_run(self, mock_typer, mock_popen):
        sync(config=".ai-sync.json", dry_run=True, detach=True)

        cmd = mock_popen.call_args[0][0]
        assert "--dry-run" in cmd


class TestGuardCommand:
    """Tests for the guard CLI command.

    guard() imports AppConfig inside the function body via
    ``from ...config import AppConfig``, so the patch target is
    ``src.config.AppConfig``, not ``src.cli.commands.sync_guard.AppConfig``.
    """

    @patch("src.config.AppConfig")
    @patch("src.cli.commands.sync_guard.AIContextSync")
    @patch("src.cli.commands.sync_guard.typer")
    def test_guard_compliant(self, mock_typer, mock_sync_cls, mock_config_cls):
        mock_config = MagicMock()
        mock_config.settings.overridden_violations = []
        mock_config_cls.load.return_value = mock_config

        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "filtered"
        mock_sync.guard.check_drift_json.return_value = []

        guard(config=".ai-sync.json")

        mock_typer.echo.assert_called_once()
        assert "compliant" in mock_typer.echo.call_args[0][0].lower()

    @patch("src.config.AppConfig")
    @patch("src.cli.commands.sync_guard.AIContextSync")
    @patch("src.cli.commands.sync_guard.typer")
    def test_guard_drift_detected(self, mock_typer, mock_sync_cls, mock_config_cls):
        mock_config = MagicMock()
        mock_config.settings.overridden_violations = []
        mock_config_cls.load.return_value = mock_config

        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "filtered"
        mock_sync.guard.check_drift_json.return_value = [
            {"rule_id": "R001", "severity": "critical", "description": "Drift detected"}
        ]

        guard(config=".ai-sync.json")

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("Drift Detected" in c for c in calls)

    @patch("src.config.AppConfig")
    @patch("src.cli.commands.sync_guard.AIContextSync")
    @patch("src.cli.commands.sync_guard.typer")
    def test_guard_overridden_violations_filtered(self, mock_typer, mock_sync_cls, mock_config_cls):
        mock_config = MagicMock()
        mock_config.settings.overridden_violations = ["R001"]
        mock_config_cls.load.return_value = mock_config

        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync.analyzer.filter_diff.return_value = "filtered"
        mock_sync.guard.check_drift_json.return_value = [
            {"rule_id": "R001", "severity": "critical", "description": "Drift detected"}
        ]

        guard(config=".ai-sync.json")

        mock_typer.echo.assert_called_once()
        assert "compliant" in mock_typer.echo.call_args[0][0].lower()
