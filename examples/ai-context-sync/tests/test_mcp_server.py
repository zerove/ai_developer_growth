"""Tests for MCP Server tools.

Tests the tool handlers registered via the handlers module.
Since tools are defined inside register() functions, we create a mock MCP
server and register the handlers to test them directly.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.exceptions import AISyncError
from src.handlers import register_tools


class MockMCP:
    """Minimal mock of FastMCP that captures registered tools."""

    def __init__(self):
        self.tools = {}
        self.resources = {}

    def tool(self):
        """Decorator that registers a tool function."""
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

    def resource(self, uri):
        """Decorator that registers a resource function."""
        def decorator(func):
            self.resources[uri] = func
            return func
        return decorator


@pytest.fixture
def mcp_server():
    """Create a mock MCP server with all tools registered."""
    mcp = MockMCP()

    mock_sync = MagicMock()
    mock_sync.config.settings.adr_dir = "docs/adr/"
    mock_sync.config.settings.context_file = "CONTEXT.md"
    mock_sync.guard_check.return_value = "All checks passed."
    mock_sync.spec_audit.return_value = "No spec violations."
    mock_sync.analyzer.get_last_commit_diff.return_value = ""
    mock_sync.analyzer.get_last_commit_message.return_value = ""
    mock_sync.analyzer.filter_diff.return_value = ""
    mock_sync.get_aggregated_context.return_value = ""
    mock_sync.orchestrator.run_flow.return_value = {"status": "done"}
    mock_sync.evolution.analyze_conflicts.return_value = []
    mock_sync.evolution.propose_evolution.return_value = "proposal text"
    mock_sync.evolution.propose_batch_evolution.return_value = "batch proposal"

    def get_sync_tool(config=".ai-sync.json", dry_run=False):
        return mock_sync

    register_tools(mcp, get_sync_tool)

    return mcp, mock_sync


class TestAiSync:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        result = mcp.tools["ai_sync"]()
        data = json.loads(result)
        assert data["status"] == "success"
        mock_sync.sync.assert_called_once()

    def test_error_handling(self):
        def failing_get_sync_tool(config=".ai-sync.json", dry_run=False):
            raise AISyncError("test error")

        mcp = MockMCP()
        register_tools(mcp, failing_get_sync_tool)
        result = mcp.tools["ai_sync"]()
        data = json.loads(result)
        assert data["status"] == "error"
        assert "test error" in data["error"]


class TestAiGuard:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        result = mcp.tools["ai_guard"]()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        mock_sync.guard_check.assert_called_once()

    def test_error_handling(self):
        def failing_get_sync_tool(config=".ai-sync.json"):
            raise AISyncError("guard error")

        mcp = MockMCP()
        register_tools(mcp, failing_get_sync_tool)
        result = mcp.tools["ai_guard"]()
        data = json.loads(result)
        assert data["status"] == "error"


class TestAiAudit:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        result = mcp.tools["ai_audit"]()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        mock_sync.spec_audit.assert_called_once()

    def test_strict_mode(self, mcp_server):
        mcp, mock_sync = mcp_server
        mock_sync.auditor.audit.return_value = []
        result = mcp.tools["ai_audit"](strict=True)
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert "critical_violations" in data


class TestAiFlow:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        result = mcp.tools["ai_flow"](task="implement feature X")
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"


class TestAiTrace:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        mock_sync.graph.trace_causality.return_value = ["ADR-001"]
        result = mcp.tools["ai_trace"](adr_id="ADR-001")
        data = json.loads(result)
        assert data["status"] in ("success", "not_found")

    def test_error_handling(self):
        def failing_get_sync_tool(config=".ai-sync.json"):
            raise Exception("trace error")

        mcp = MockMCP()
        register_tools(mcp, failing_get_sync_tool)
        result = mcp.tools["ai_trace"](adr_id="ADR-999")
        data = json.loads(result)
        assert data["status"] == "error"


class TestAiMap:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        result = mcp.tools["ai_map"]()
        data = json.loads(result)
        assert data["status"] == "success"
        assert "mermaid" in data


class TestAiEvolve:
    def test_success(self, mcp_server):
        mcp, mock_sync = mcp_server
        mock_sync.evolution.analyze_conflicts.return_value = []
        result = mcp.tools["ai_evolve"]()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert data["candidates"] == []

    def test_with_candidates(self, mcp_server):
        mcp, mock_sync = mcp_server
        mock_sync.evolution.analyze_conflicts.return_value = [{"rule_id": "R1", "ratio": 0.8}]
        mock_sync.evolution.propose_evolution.return_value = "proposal text"
        result = mcp.tools["ai_evolve"]()
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert len(data["proposals"]) == 1

    def test_batch_mode(self, mcp_server):
        mcp, mock_sync = mcp_server
        mock_sync.evolution.analyze_conflicts.return_value = [{"rule_id": "R1", "ratio": 0.8}]
        mock_sync.evolution.propose_batch_evolution.return_value = "batch proposal"
        result = mcp.tools["ai_evolve"](batch=True)
        data = json.loads(result)
        assert data["status"] == "success", f"Unexpected: {data}"
        assert "batch_proposal" in data
