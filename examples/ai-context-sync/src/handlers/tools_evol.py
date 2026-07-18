"""MCP tool handlers: evolve, scaffold.

Registered via register(mcp, get_sync_tool) to avoid circular imports.
"""

from __future__ import annotations

import json
from typing import Callable


def register(mcp: object, get_sync_tool: Callable) -> None:
    """Register evolve/scaffold tool handlers."""

    @mcp.tool()
    def ai_evolve(config: str = ".ai-sync.json", batch: bool = False) -> str:
        """Analyze audit history and propose updates to project specifications.

        Examines override patterns and violation history to detect when a spec
        rule is consistently overridden — indicating the spec may need updating.

        Args:
            config: Path to the .ai-sync.json configuration file.
            batch: If true, generate a single batch proposal for all candidates.
        """
        try:
            sync_tool = get_sync_tool(config=config)
            candidates = sync_tool.evolution.analyze_conflicts()

            if not candidates:
                return json.dumps({
                    "status": "success",
                    "candidates": [],
                    "message": "No evolution opportunities detected."
                })

            if batch:
                proposal = sync_tool.evolution.propose_batch_evolution(candidates)
                return json.dumps({
                    "status": "success",
                    "candidates": candidates,
                    "batch_proposal": proposal
                })

            proposals = []
            for c in candidates:
                proposal = sync_tool.evolution.propose_evolution(c)
                proposals.append({
                    "rule_id": c["rule_id"],
                    "ratio": c["ratio"],
                    "proposal": proposal
                })

            return json.dumps({
                "status": "success",
                "candidates": candidates,
                "proposals": proposals
            })
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @mcp.tool()
    def ai_scaffold(template: str, target_dir: str = ".", config: str = ".ai-sync.json") -> str:
        """Initialize a project from a template.

        Creates directory structure, CONTEXT.md, and specs based on a template.

        Args:
            template: Template name (e.g. 'python-fastapi', 'react-typescript').
            target_dir: Target directory for scaffolding.
            config: Path to the .ai-sync.json configuration file.
        """
        try:
            sync_tool = get_sync_tool(config=config, dry_run=False)
            from src.onboarding import OnboardingSession
            session = OnboardingSession(sync_tool.llm_client, root_dir=target_dir)
            session.start()
            return json.dumps({"status": "success", "template": template, "target": target_dir})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})
