"""MCP tool handlers: flow, trace, explain.

Registered via register(mcp, get_sync_tool) to avoid circular imports.
"""

from __future__ import annotations

import json
import os
from typing import Callable

from ..exceptions import LLMError


def register(mcp: object, get_sync_tool: Callable) -> None:
    """Register flow/trace/explain tool handlers."""

    @mcp.tool()
    def ai_flow(task: str, config: str = ".ai-sync.json") -> str:
        """Execute the full AI-Native development flow for a specific task.

        Runs the complete Sense -> Design -> Implement -> Audit -> Sync pipeline.
        The flow generates a design, decomposes into sub-tasks, implements them
        in parallel with test verification, audits compliance, and syncs context.

        Args:
            task: Description of the task to implement.
            config: Path to the .ai-sync.json configuration file.
        """
        try:
            sync_tool = get_sync_tool(config=config)

            from src.slicer import ContextSlicer

            ContextSlicer()
            diff = sync_tool.analyzer.get_last_commit_diff()
            filtered_diff = sync_tool.analyzer.filter_diff(diff)

            affected_files = []
            if filtered_diff:
                for line in filtered_diff.splitlines():
                    if line.startswith("+++ b/"):
                        affected_files.append(line[6:])

            aggregated_context = sync_tool.get_aggregated_context(affected_files)
            if not aggregated_context:
                root_context_path = sync_tool.config.settings.context_file
                if os.path.exists(root_context_path):
                    with open(root_context_path, "r", encoding="utf-8") as f:
                        aggregated_context = f.read()

            def approval_callback() -> bool:
                return True

            result = sync_tool.orchestrator.run_flow(task, approval_callback, initial_context=aggregated_context)
            return json.dumps({"status": "success", "result": result})
        except (LLMError, OSError, json.JSONDecodeError, KeyError) as e:
            return json.dumps({"status": "error", "error": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @mcp.tool()
    def ai_trace(adr_id: str, config: str = ".ai-sync.json") -> str:
        """Trace the causal chain leading to a specific architectural decision.

        Follows dependency links (Depends-On, Supersedes) backwards from the
        given ADR to show the full decision history.

        Args:
            adr_id: The ADR ID to trace (e.g. 'ADR-003').
            config: Path to the .ai-sync.json configuration file.
        """
        try:
            sync_tool = get_sync_tool(config=config)
            from src.graph import DecisionGraph

            graph = DecisionGraph(sync_tool.config.settings.adr_dir)
            chain = graph.trace_causality(adr_id)

            if not chain:
                return json.dumps(
                    {
                        "status": "not_found",
                        "adr_id": adr_id,
                        "message": f"No causal chain found for {adr_id}",
                    }
                )

            nodes = []
            for node_id in chain:
                title = graph.nodes[node_id].title if node_id in graph.nodes else "Unknown"
                nodes.append({"id": node_id, "title": title})

            return json.dumps({"status": "success", "adr_id": adr_id, "chain": nodes})
        except (LLMError, OSError, json.JSONDecodeError, KeyError) as e:
            return json.dumps({"status": "error", "error": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @mcp.tool()
    def ai_explain(query: str, config: str = ".ai-sync.json") -> str:
        """Explain an architectural decision using ADR context.

        Uses semantic search to find relevant ADRs and LLM to synthesize
        a comprehensive explanation of the decision rationale.

        Args:
            query: Question about architectural decisions (e.g. 'Why PostgreSQL?').
            config: Path to the .ai-sync.json configuration file.
        """
        try:
            sync_tool = get_sync_tool(config=config)
            from src.reasoning import DecisionReasoner

            reasoner = DecisionReasoner(sync_tool.llm_client, sync_tool.config.settings.adr_dir)
            result = reasoner.explain_decision(query)
            return json.dumps({"status": "success", "explanation": result})
        except (LLMError, OSError, json.JSONDecodeError) as e:
            return json.dumps({"status": "error", "error": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})
