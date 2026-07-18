"""AI-Context-Sync MCP Server.

Exposes AI-Context-Sync capabilities as MCP tools for opencode agents.
Tools: sync, guard, audit, flow, trace, evolve, scaffold, explain.
Resources: context, adr, specs.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.core import AIContextSync
from src.exceptions import AISyncError

mcp = FastMCP("AI-Context-Sync")


def _get_sync_tool(config: str = ".ai-sync.json", dry_run: bool = False) -> AIContextSync:
    return AIContextSync(config_path=config, dry_run=dry_run)


@mcp.resource("context://{config_path}")
def get_context(config_path: str = ".ai-sync.json") -> str:
    """Read the project CONTEXT.md file."""
    try:
        sync_tool = _get_sync_tool(config=config_path)
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
        sync_tool = _get_sync_tool()
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
        sync_tool = _get_sync_tool()
        specs_dir = sync_tool.config.settings.specs_dir
        spec_file = os.path.join(specs_dir, f"{language.lower()}.md")
        if os.path.exists(spec_file):
            with open(spec_file, "r", encoding="utf-8") as f:
                return f.read()
        available = [f[:-3] for f in os.listdir(specs_dir) if f.endswith(".md")] if os.path.exists(specs_dir) else []
        return f"No spec for {language}. Available: {available}"
    except (AISyncError, OSError) as e:
        return f"Error: {e}"


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
        sync_tool = _get_sync_tool(config=config, dry_run=dry_run)
        sync_tool.sync()
        return json.dumps({"status": "success", "config": config, "dry_run": dry_run})
    except Exception as e:
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
        sync_tool = _get_sync_tool(config=config)
        report = sync_tool.guard_check()
        return json.dumps({"status": "success", "report": report})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def ai_audit(config: str = ".ai-sync.json", strict: bool = False) -> str:
    """Audit current code changes against language-specific development specifications.

    Checks the last commit diff against project specs and returns violations.
    In strict mode, returns only Critical violations.

    Args:
        config: Path to the .ai-sync.json configuration file.
        strict: If true, only return Critical-level violations.
    """
    try:
        sync_tool = _get_sync_tool(config=config)
        report = sync_tool.spec_audit()
        if strict:
            from src.auditor import Violation
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
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


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
        sync_tool = _get_sync_tool(config=config)

        from src.slicer import ContextSlicer
        slicer = ContextSlicer()
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

        result = sync_tool.orchestrator.run_flow(
            task, approval_callback, initial_context=aggregated_context
        )
        return json.dumps({"status": "success", "result": result})
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
        sync_tool = _get_sync_tool(config=config)
        from src.graph import DecisionGraph
        graph = DecisionGraph(sync_tool.config.settings.adr_dir)
        chain = graph.trace_causality(adr_id)

        if not chain:
            return json.dumps({
                "status": "not_found",
                "adr_id": adr_id,
                "message": f"No causal chain found for {adr_id}"
            })

        nodes = []
        for node_id in chain:
            title = graph.nodes[node_id].title if node_id in graph.nodes else "Unknown"
            nodes.append({"id": node_id, "title": title})

        return json.dumps({
            "status": "success",
            "adr_id": adr_id,
            "chain": nodes
        })
    except Exception as e:
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
        sync_tool = _get_sync_tool(config=config)
        from src.graph import DecisionGraph
        graph = DecisionGraph(sync_tool.config.settings.adr_dir)
        mermaid = graph.generate_mermaid()
        return json.dumps({
            "status": "success",
            "mermaid": mermaid,
            "adr_dir": sync_tool.config.settings.adr_dir
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


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
        sync_tool = _get_sync_tool(config=config)
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
        sync_tool = _get_sync_tool(config=config, dry_run=False)
        from src.onboarding import OnboardingSession
        session = OnboardingSession(sync_tool.llm_client, root_dir=target_dir)
        session.start()
        return json.dumps({"status": "success", "template": template, "target": target_dir})
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
        sync_tool = _get_sync_tool(config=config)
        from src.reasoning import DecisionReasoner
        reasoner = DecisionReasoner(sync_tool.llm_client, sync_tool.config.settings.adr_dir)
        result = reasoner.explain_decision(query)
        return json.dumps({"status": "success", "explanation": result})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


if __name__ == "__main__":
    mcp.run()
