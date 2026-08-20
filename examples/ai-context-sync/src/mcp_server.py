"""AI-Context-Sync MCP Server.

Exposes AI-Context-Sync capabilities as MCP tools for opencode agents.
Tools: sync, guard, audit, flow, trace, evolve, scaffold, explain.
Resources: context, adr, specs.
"""

from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

# Add project root to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ruff: noqa: E402
from src.core import AIContextSync
from src.handlers import register_resources, register_tools

mcp = FastMCP("AI-Context-Sync")


def _get_sync_tool(
    config: str = ".ai-sync.json", dry_run: bool = False
) -> AIContextSync:
    return AIContextSync(config_path=config, dry_run=dry_run)


# Register all tool and resource handlers
register_tools(mcp, _get_sync_tool)
register_resources(mcp, _get_sync_tool)


if __name__ == "__main__":
    mcp.run()
