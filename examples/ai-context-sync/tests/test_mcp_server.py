"""Tests for MCP Server tools."""

import json
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mock_sync():
    """Patch _get_sync_tool to return a mock AIContextSync."""
    mock = MagicMock()
    mock.config.settings.adr_dir = "docs/adr/"
    mock.config.settings.context_file = "CONTEXT.md"
    # String-returning methods
    mock.guard_check.return_value = "All checks passed."
    mock.spec_audit.return_value = "No spec violations."
    mock.analyzer.get_last_commit_diff.return_value = ""
    mock.analyzer.get_last_commit_message.return_value = ""
    mock.analyzer.filter_diff.return_value = ""
    mock.get_aggregated_context.return_value = ""
    mock.orchestrator.run_flow.return_value = {"status": "done"}
    mock.graph = MagicMock()
    mock.graph.trace_causality.return_value = ["ADR-001"]
    mock.graph.nodes = {}
    mock.graph.generate_mermaid.return_value = "graph TD; A-->B"
    with patch("src.mcp_server._get_sync_tool", return_value=mock):
        yield mock


class TestAiSync:
    def test_success(self, mock_sync):
        from src.mcp_server import ai_sync
        result = ai_sync()
        data = json.loads(result)
        assert data["status"] == "success"
        mock_sync.sync.assert_called_once()

    def test_error_handling(self):
        from src.mcp_server import ai_sync
        with patch("src.mcp_server._get_sync_tool", side_effect=Exception("test error")):
            result = ai_sync()
            data = json.loads(result)
            assert data["status"] == "error"
            assert "test error" in data["error"]


class TestAiGuard:
    def test_success(self, mock_sync):
        from src.mcp_server import ai_guard
        result = ai_guard()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        mock_sync.guard_check.assert_called_once()

    def test_error_handling(self):
        from src.mcp_server import ai_guard
        with patch("src.mcp_server._get_sync_tool", side_effect=Exception("guard error")):
            result = ai_guard()
            data = json.loads(result)
            assert data["status"] == "error"


class TestAiAudit:
    def test_success(self, mock_sync):
        from src.mcp_server import ai_audit
        result = ai_audit()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        mock_sync.spec_audit.assert_called_once()

    def test_strict_mode(self, mock_sync):
        mock_sync.auditor.audit.return_value = []
        from src.mcp_server import ai_audit
        result = ai_audit(strict=True)
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert "critical_violations" in data


class TestAiFlow:
    def test_success(self, mock_sync):
        from src.mcp_server import ai_flow
        result = ai_flow(task="implement feature X")
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"


class TestAiTrace:
    def test_success(self, mock_sync):
        from src.mcp_server import ai_trace
        result = ai_trace(adr_id="ADR-001")
        data = json.loads(result)
        assert data["status"] in ("success", "not_found")

    def test_error_handling(self):
        from src.mcp_server import ai_trace
        with patch("src.mcp_server._get_sync_tool", side_effect=Exception("trace error")):
            result = ai_trace(adr_id="ADR-999")
            data = json.loads(result)
            assert data["status"] == "error"


class TestAiMap:
    def test_success(self, mock_sync):
        from src.mcp_server import ai_map
        result = ai_map()
        data = json.loads(result)
        assert data["status"] == "success"
        assert "mermaid" in data


class TestAiEvolve:
    def test_success(self, mock_sync):
        mock_sync.evolution.analyze_conflicts.return_value = []
        from src.mcp_server import ai_evolve
        result = ai_evolve()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert data["candidates"] == []

    def test_with_candidates(self, mock_sync):
        mock_sync.evolution.analyze_conflicts.return_value = [{"rule_id": "R1", "ratio": 0.8}]
        mock_sync.evolution.propose_evolution.return_value = "proposal text"
        from src.mcp_server import ai_evolve
        result = ai_evolve()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert len(data["proposals"]) == 1

    def test_batch_mode(self, mock_sync):
        mock_sync.evolution.analyze_conflicts.return_value = [{"rule_id": "R1", "ratio": 0.8}]
        mock_sync.evolution.propose_batch_evolution.return_value = "batch proposal"
        from src.mcp_server import ai_evolve
        result = ai_evolve(batch=True)
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert "batch_proposal" in data
