"""Tests for src/cli/commands/flow.py — flow command (with/without diff, context fallback)."""

from unittest.mock import MagicMock, mock_open, patch

from src.cli.commands.flow import flow


class TestFlowCommand:
    """Tests for the flow CLI command."""

    @patch("src.cli.commands.flow.typer")
    @patch("src.cli.commands.flow.AIContextSync")
    def test_flow_with_diff(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff\n"
        mock_sync.analyzer.filter_diff.return_value = "+++ b/src/main.py\n"
        mock_sync.get_aggregated_context.return_value = "context from diff"
        mock_sync.orchestrator.run_flow.return_value = "flow result"

        flow(task="refactor auth", config=".ai-sync.json")

        mock_sync.orchestrator.run_flow.assert_called_once()
        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("flow result" in c for c in calls)

    @patch("src.cli.commands.flow.os.path.exists", return_value=False)
    @patch("src.cli.commands.flow.typer")
    @patch("src.cli.commands.flow.AIContextSync")
    def test_flow_without_diff_no_context_file(self, mock_sync_cls, mock_typer, mock_exists):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""
        mock_sync.analyzer.filter_diff.return_value = ""
        mock_sync.get_aggregated_context.return_value = ""
        mock_sync.orchestrator.run_flow.return_value = "flow result"

        flow(task="new feature", config=".ai-sync.json")

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("flow result" in c for c in calls)

    @patch("src.cli.commands.flow.os.path.exists", return_value=True)
    @patch("src.cli.commands.flow.open", mock_open(read_data="# Context\n\nRoot context."))
    @patch("src.cli.commands.flow.typer")
    @patch("src.cli.commands.flow.AIContextSync")
    def test_flow_without_diff_fallback_to_context_file(self, mock_sync_cls, mock_typer, mock_exists):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""
        mock_sync.analyzer.filter_diff.return_value = ""
        mock_sync.get_aggregated_context.return_value = ""
        mock_sync.orchestrator.run_flow.return_value = "flow result"

        flow(task="update deps", config=".ai-sync.json")

        mock_sync.orchestrator.run_flow.assert_called_once()
        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("flow result" in c for c in calls)
