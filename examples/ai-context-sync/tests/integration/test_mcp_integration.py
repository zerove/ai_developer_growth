"""Integration tests for MCP server tools.

Tests the full flow of MCP tool registration and execution.
"""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.core import AIContextSync
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
def temp_project():
    """Create a temporary project directory with minimal config."""
    tmpdir = tempfile.mkdtemp()
    config_path = os.path.join(tmpdir, ".ai-sync.json")

    config = {
        "llm": {"provider": "openai", "model": "gpt-4o"},
        "settings": {"context_file": os.path.join(tmpdir, "CONTEXT.md"), "adr_dir": os.path.join(tmpdir, "docs/adr")},
    }

    with open(config_path, "w") as f:
        json.dump(config, f)

    with open(os.path.join(tmpdir, "CONTEXT.md"), "w") as f:
        f.write("# Test Context\nThis is a test project.")

    os.makedirs(os.path.join(tmpdir, "docs/adr"), exist_ok=True)

    yield tmpdir, config_path

    shutil.rmtree(tmpdir, ignore_errors=True)


class TestMCPIntegration:
    def test_tool_registration(self, temp_project):
        tmpdir, config_path = temp_project

        mcp = MockMCP()
        sync = AIContextSync(config_path=config_path, dry_run=True)

        def get_sync_tool(config=".ai-sync.json", dry_run=False):
            return sync

        register_tools(mcp, get_sync_tool)

        expected_tools = [
            "ai_sync",
            "ai_guard",
            "ai_audit",
            "ai_map",
            "ai_flow",
            "ai_trace",
            "ai_explain",
            "ai_evolve",
            "ai_scaffold",
        ]

        for tool_name in expected_tools:
            assert tool_name in mcp.tools, f"Tool {tool_name} not registered"

    def test_ai_sync_integration(self, temp_project):
        tmpdir, config_path = temp_project

        mcp = MockMCP()
        sync = AIContextSync(config_path=config_path, dry_run=True)

        def get_sync_tool(config=".ai-sync.json", dry_run=False):
            return sync

        register_tools(mcp, get_sync_tool)

        result = mcp.tools["ai_sync"](config=config_path)
        data = json.loads(result)

        assert data["status"] == "success"
        assert data["config"] == config_path

    def test_ai_guard_integration(self, temp_project):
        tmpdir, config_path = temp_project

        mcp = MockMCP()
        sync = AIContextSync(config_path=config_path, dry_run=True)

        def get_sync_tool(config=".ai-sync.json", dry_run=False):
            return sync

        register_tools(mcp, get_sync_tool)

        result = mcp.tools["ai_guard"](config=config_path)
        data = json.loads(result)

        assert data["status"] == "success"
        assert "report" in data

    def test_ai_audit_integration(self, temp_project):
        tmpdir, config_path = temp_project

        mcp = MockMCP()
        sync = AIContextSync(config_path=config_path, dry_run=True)

        def get_sync_tool(config=".ai-sync.json", dry_run=False):
            return sync

        register_tools(mcp, get_sync_tool)

        result = mcp.tools["ai_audit"](config=config_path)
        data = json.loads(result)

        assert data["status"] == "success"
        assert "report" in data

    def test_ai_map_integration(self, temp_project):
        tmpdir, config_path = temp_project

        mcp = MockMCP()
        sync = AIContextSync(config_path=config_path, dry_run=True)

        def get_sync_tool(config=".ai-sync.json", dry_run=False):
            return sync

        register_tools(mcp, get_sync_tool)

        result = mcp.tools["ai_map"](config=config_path)
        data = json.loads(result)

        assert data["status"] == "success"
        assert "mermaid" in data

    def test_ai_evolve_integration(self, temp_project):
        tmpdir, config_path = temp_project

        mcp = MockMCP()
        sync = AIContextSync(config_path=config_path, dry_run=True)

        def get_sync_tool(config=".ai-sync.json", dry_run=False):
            return sync

        register_tools(mcp, get_sync_tool)

        result = mcp.tools["ai_evolve"](config=config_path)
        data = json.loads(result)

        assert data["status"] == "success"
        assert "candidates" in data
