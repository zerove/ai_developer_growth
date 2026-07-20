"""MCP tool handlers: sync, guard, audit, map.

Registered via register(mcp, get_sync_tool) to avoid circular imports.
"""

from __future__ import annotations

import json
from typing import Callable

from ..exceptions import AISyncError


def register(mcp: object, get_sync_tool: Callable) -> None:
    """Register sync/guard/audit/map tool handlers."""

    @mcp.tool()
    def ai_sync(config: str = ".ai-sync.json", dry_run: bool = False) -> str:
        """Synchronize project context (CONTEXT.md) from the latest git commit.

        Analyzes the last commit diff, synthesizes updates to the project's
        CONTEXT.md file, and optionally generates an ADR if the commit message
        contains '#ADR'.

        Args:
            config: Path to the .ai-sync.json configuration file.
            dry_run: If true, simulate without writing files.
        """
        try:
            sync_tool = get_sync_tool(config=config, dry_run=dry_run)
            sync_tool.sync()
            return json.dumps({"status": "success", "config": config, "dry_run": dry_run})
        except AISyncError as e:
            return json.dumps({"status": "error", "error": str(e)})

    @mcp.tool()
    def ai_guard(config: str = ".ai-sync.json") -> str:
        """Audit current code changes against Architecture Decision Records (ADRs).

        Compares the last commit diff and message against all ADRs to detect
        architectural drift. Returns a list of violations found.

        Args:
            config: Path to the .ai-sync.json configuration file.
        """
        try:
            sync_tool = get_sync_tool(config=config)
            report = sync_tool.guard_check()
            return json.dumps({"status": "success", "report": report})
        except AISyncError as e:
            return json.dumps({"status": "error", "error": str(e)})

    @mcp.tool()
    def ai_audit(config: str = ".ai-sync.json", strict: bool = False) -> str:
        """Audit current code changes against development specifications.

        Checks the last commit diff against project specs and returns violations.
        In strict mode, returns only Critical violations.

        Args:
            config: Path to the .ai-sync.json configuration file.
            strict: If true, only return Critical-level violations.
        """
        try:
            sync_tool = get_sync_tool(config=config)
            report = sync_tool.spec_audit()
            if strict:
                violations = sync_tool.auditor.audit(
                    sync_tool.analyzer.get_last_commit_diff(),
                    sync_tool.analyzer.get_last_commit_message()
                )
                critical = [v.to_dict() for v in violations if v.severity == "Critical"]
                return json.dumps({
                    "status": "success",
                    "report": report,
                    "critical_violations": critical
                })
            return json.dumps({"status": "success", "report": report})
        except AISyncError as e:
            return json.dumps({"status": "error", "error": str(e)})

    @mcp.tool()
    def ai_map(config: str = ".ai-sync.json") -> str:
        """Generate a Mermaid diagram of the Architecture Decision Map.

        Parses all ADRs and creates a visual dependency graph showing
        how decisions relate to each other.

        Args:
            config: Path to the .ai-sync.json configuration file.
        """
        try:
            sync_tool = get_sync_tool(config=config)
            from src.graph import DecisionGraph
            graph = DecisionGraph(sync_tool.config.settings.adr_dir)
            mermaid = graph.generate_mermaid()
            return json.dumps({
                "status": "success",
                "mermaid": mermaid,
                "adr_dir": sync_tool.config.settings.adr_dir
            })
        except AISyncError as e:
            return json.dumps({"status": "error", "error": str(e)})
