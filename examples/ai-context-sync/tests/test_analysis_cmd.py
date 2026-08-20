"""Tests for CLI analysis commands: trace, map, why."""

import os
import sys
from unittest.mock import MagicMock, mock_open, patch

from typer.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# trace
# ---------------------------------------------------------------------------


class TestTrace:
    """Tests for the trace command."""

    @patch("src.cli.commands.analysis.AIContextSync")
    @patch("src.cli.commands.analysis.DecisionGraph")
    def test_trace_valid_chain(self, mock_graph_cls, mock_sync_cls):
        """Trace displays causal chain for a valid ADR ID."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = "docs/adr/"
        mock_sync_cls.return_value = mock_sync

        mock_graph = MagicMock()
        mock_graph.trace_causality.return_value = ["ADR-001", "ADR-002", "ADR-003"]
        mock_graph.nodes = {
            "ADR-001": MagicMock(title="Use REST API"),
            "ADR-002": MagicMock(title="Add Authentication"),
            "ADR-003": MagicMock(title="OAuth2 Migration"),
        }
        mock_graph_cls.return_value = mock_graph

        result = runner.invoke(app, ["trace", "ADR-003"])

        assert result.exit_code == 0
        assert "Causal Trace for ADR-003" in result.stdout
        assert "Use REST API" in result.stdout
        assert "OAuth2 Migration" in result.stdout
        assert "Conclusion" in result.stdout

    @patch("src.cli.commands.analysis.AIContextSync")
    @patch("src.cli.commands.analysis.DecisionGraph")
    def test_trace_invalid_adr(self, mock_graph_cls, mock_sync_cls):
        """Trace shows error for non-existent ADR ID."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = "docs/adr/"
        mock_sync_cls.return_value = mock_sync

        mock_graph = MagicMock()
        mock_graph.trace_causality.return_value = []
        mock_graph_cls.return_value = mock_graph

        result = runner.invoke(app, ["trace", "ADR-999"])

        assert result.exit_code == 0
        assert "Could not find causal chain" in result.stdout

    @patch("src.cli.commands.analysis.AIContextSync")
    @patch("src.cli.commands.analysis.DecisionGraph")
    def test_trace_unknown_node_title(self, mock_graph_cls, mock_sync_cls):
        """Trace shows 'Unknown' for nodes not in graph.nodes dict."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = "docs/adr/"
        mock_sync_cls.return_value = mock_sync

        mock_graph = MagicMock()
        mock_graph.trace_causality.return_value = ["ADR-001", "ADR-099"]
        mock_graph.nodes = {
            "ADR-001": MagicMock(title="Use REST API"),
            # ADR-099 deliberately missing
        }
        mock_graph_cls.return_value = mock_graph

        result = runner.invoke(app, ["trace", "ADR-099"])

        assert result.exit_code == 0
        assert "Unknown" in result.stdout


# ---------------------------------------------------------------------------
# map
# ---------------------------------------------------------------------------


class TestMap:
    """Tests for the map command."""

    @patch("src.cli.commands.analysis.os.makedirs")
    @patch("src.cli.commands.analysis.AIContextSync")
    @patch("src.cli.commands.analysis.DecisionGraph")
    def test_map_generates_mermaid(self, mock_graph_cls, mock_sync_cls, mock_makedirs):
        """Map generates Mermaid diagram and writes to file."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = "docs/adr/"
        mock_sync_cls.return_value = mock_sync

        mock_graph = MagicMock()
        mock_graph.generate_mermaid.return_value = "graph TD\n  A-->B"
        mock_graph_cls.return_value = mock_graph

        with patch("builtins.open", mock_open()) as m_open:
            result = runner.invoke(app, ["map"])

            assert result.exit_code == 0
            assert "Architecture map generated" in result.stdout
            mock_graph.generate_mermaid.assert_called_once()
            m_open.assert_called_once_with(
                "docs/architecture_map.md", "w", encoding="utf-8"
            )


# ---------------------------------------------------------------------------
# why
# ---------------------------------------------------------------------------


class TestWhy:
    """Tests for the why command."""

    @patch("src.cli.commands.analysis.AIContextSync")
    @patch("src.reasoning.DecisionReasoner", create=True)
    def test_why_explains_decision(self, mock_reasoner_cls, mock_sync_cls):
        """Why returns explanation for a query."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = "docs/adr/"
        mock_sync.llm_client = MagicMock()
        mock_sync_cls.return_value = mock_sync

        mock_reasoner = MagicMock()
        mock_reasoner.explain_decision.return_value = "We chose REST because..."
        mock_reasoner_cls.return_value = mock_reasoner

        result = runner.invoke(app, ["why", "Why REST?"])

        assert result.exit_code == 0
        assert "Decision Explanation" in result.stdout
        assert "We chose REST because..." in result.stdout
        mock_reasoner.explain_decision.assert_called_once_with("Why REST?")

    @patch("src.cli.commands.analysis.AIContextSync")
    @patch("src.reasoning.DecisionReasoner", create=True)
    def test_why_with_empty_query(self, mock_reasoner_cls, mock_sync_cls):
        """Why handles empty query string gracefully."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = "docs/adr/"
        mock_sync.llm_client = MagicMock()
        mock_sync_cls.return_value = mock_sync

        mock_reasoner = MagicMock()
        mock_reasoner.explain_decision.return_value = (
            "Please provide a specific question."
        )
        mock_reasoner_cls.return_value = mock_reasoner

        result = runner.invoke(app, ["why", ""])

        assert result.exit_code == 0
        assert "Decision Explanation" in result.stdout
