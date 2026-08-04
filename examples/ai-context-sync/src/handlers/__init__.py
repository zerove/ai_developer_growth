"""Handler registration for AI-Context-Sync MCP server.

Provides register_tools() and register_resources() to attach all
handlers to a FastMCP instance without circular imports.
"""

from __future__ import annotations

from typing import Callable

from src.handlers.resources import register as register_resources
from src.handlers.tools_core import register as _register_core
from src.handlers.tools_evol import register as _register_evol
from src.handlers.tools_flow import register as _register_flow


def register_tools(mcp: object, get_sync_tool: Callable) -> None:
    """Register all tool handlers (9 total) with the MCP server."""
    _register_core(mcp, get_sync_tool)
    _register_flow(mcp, get_sync_tool)
    _register_evol(mcp, get_sync_tool)


__all__ = ["register_tools", "register_resources"]
