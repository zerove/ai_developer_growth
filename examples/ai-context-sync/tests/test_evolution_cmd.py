"""Tests for src/cli/commands/evolution.py — evolve command (batch, interactive, no candidates)."""
from unittest.mock import MagicMock, patch

from src.cli.commands.evolution import evolve


class TestEvolveCommand:
    """Tests for the evolve CLI command."""

    @patch("src.cli.commands.evolution.typer")
    @patch("src.cli.commands.evolution.AIContextSync")
    def test_evolve_no_candidates(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_sync.evolution.analyze_conflicts.return_value = []

        evolve(config=".ai-sync.json", batch=False)

        mock_typer.echo.assert_called_once()
        assert "No strong patterns" in mock_typer.echo.call_args[0][0]

    @patch("src.cli.commands.evolution.typer")
    @patch("src.cli.commands.evolution.AIContextSync")
    def test_evolve_batch_mode(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        candidates = [{"rule_id": "R001", "ratio": 0.8}]
        mock_sync.evolution.analyze_conflicts.return_value = candidates
        mock_sync.evolution.propose_batch_evolution.return_value = "batch proposal"

        evolve(config=".ai-sync.json", batch=True)

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("batch mode" in c.lower() for c in calls)
        mock_sync.evolution.propose_batch_evolution.assert_called_once_with(candidates)

    @patch("src.cli.commands.evolution.typer")
    @patch("src.cli.commands.evolution.AIContextSync")
    def test_evolve_interactive_accept(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        candidates = [{"rule_id": "R001", "ratio": 0.8}]
        mock_sync.evolution.analyze_conflicts.return_value = candidates
        mock_sync.evolution.propose_evolution.return_value = "proposal text"

        mock_typer.confirm.return_value = True

        evolve(config=".ai-sync.json", batch=False)

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        assert any("accepted" in c.lower() for c in calls)

    @patch("src.cli.commands.evolution.typer")
    @patch("src.cli.commands.evolution.AIContextSync")
    def test_evolve_interactive_decline(self, mock_sync_cls, mock_typer):
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        candidates = [{"rule_id": "R001", "ratio": 0.8}]
        mock_sync.evolution.analyze_conflicts.return_value = candidates
        mock_sync.evolution.propose_evolution.return_value = "proposal text"

        mock_typer.confirm.return_value = False

        evolve(config=".ai-sync.json", batch=False)

        calls = [str(c) for c in mock_typer.echo.call_args_list]
        # Should NOT contain "accepted"
        assert not any("accepted" in c.lower() for c in calls)
