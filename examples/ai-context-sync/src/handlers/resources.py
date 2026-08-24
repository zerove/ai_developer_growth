"""MCP resource handler functions for AI-Context-Sync.

Each resource is registered via register(mcp, get_sync_tool) to avoid
circular imports with the main mcp_server module.
"""

from __future__ import annotations

import os
from typing import Callable

from src.exceptions import AISyncError


def register(mcp: object, get_sync_tool: Callable) -> None:
    """Register all resource handlers with the MCP server.

    Args:
        mcp: FastMCP server instance (uses __call__ for decorator protocol).
        get_sync_tool: Factory function returning AIContextSync instances.
    """

    @mcp.resource("context://{config_path}")
    def get_context(config_path: str = ".ai-sync.json") -> str:
        """Read the project CONTEXT.md file."""
        try:
            sync_tool = get_sync_tool(config=config_path)
            context_file = sync_tool.config.settings.context_file
            if os.path.exists(context_file):
                with open(context_file, "r", encoding="utf-8") as f:
                    return f.read()
            return f"No context file found at {context_file}"
        except AISyncError as e:
            return f"Error: {e}"

    @mcp.resource("adr://{adr_id}")
    def get_adr(adr_id: str) -> str:
        """Read a specific ADR file by ID."""
        try:
            sync_tool = get_sync_tool()
            adr_dir = sync_tool.config.settings.adr_dir
            for filename in os.listdir(adr_dir):
                if filename.endswith(".md"):
                    path = os.path.join(adr_dir, filename)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if adr_id in content:
                        return content
            return f"ADR {adr_id} not found in {adr_dir}"
        except (AISyncError, OSError) as e:
            return f"Error: {e}"

    @mcp.resource("specs://{language}")
    def get_specs(language: str = "python") -> str:
        """Read development specifications for a language."""
        try:
            sync_tool = get_sync_tool()
            specs_dir = sync_tool.config.settings.specs_dir
            spec_file = os.path.join(specs_dir, f"{language.lower()}.md")
            if os.path.exists(spec_file):
                with open(spec_file, "r", encoding="utf-8") as f:
                    return f.read()
            available = (
                [f[:-3] for f in os.listdir(specs_dir) if f.endswith(".md")] if os.path.exists(specs_dir) else []
            )
            return f"No spec for {language}. Available: {available}"
        except (AISyncError, OSError) as e:
            return f"Error: {e}"
