"""Analysis commands for AI-Context-Sync CLI."""

import os

import typer

from ...core import AIContextSync
from ...graph import DecisionGraph
from .. import cli_error_handler


@cli_error_handler
def trace(adr_id: str, config: str = typer.Option(".ai-sync.json", help="Path to config file")) -> None:
    """Trace the causal chain leading up to a specific architectural decision."""
    sync_tool = AIContextSync(config_path=config)
    graph = DecisionGraph(sync_tool.config.settings.adr_dir)
    chain = graph.trace_causality(adr_id)

    if not chain:
        typer.echo(f"❌ Could not find causal chain for {adr_id}. Please check if the ID is correct.")
        return

    typer.echo(f"\n--- Causal Trace for {adr_id} ---\n")
    for i, node_id in enumerate(chain):
        title = graph.nodes[node_id].title if node_id in graph.nodes else "Unknown"
        typer.echo(f"{i + 1}. {node_id}: {title}")
    typer.echo(f"\nConclusion: {adr_id} was decided based on the preceding sequence.")


@cli_error_handler
def map(config: str = typer.Option(".ai-sync.json", help="Path to config file")) -> None:
    """Generate a visual architecture decision map as a Mermaid diagram."""
    sync_tool = AIContextSync(config_path=config)
    graph = DecisionGraph(sync_tool.config.settings.adr_dir)
    mermaid_code = graph.generate_mermaid()

    report_path = "docs/architecture_map.md"
    os.makedirs(os.path.dirname(report_path) if os.path.dirname(report_path) else ".", exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 🗺️ Architecture Decision Map\n\n")
        f.write(f"This map is automatically generated from the ADRs in {sync_tool.config.settings.adr_dir}.\n\n")
        f.write(f"```mermaid\n{mermaid_code}\n```\n\n")
        f.write("---\n*Tip: Use a Mermaid-compatible viewer (like Zed or GitHub) to render this map.*")

    typer.echo(f"✅ Architecture map generated successfully at {report_path}")


@cli_error_handler
def why(query: str, config: str = typer.Option(".ai-sync.json", help="Path to config file")) -> None:
    """Ask 'why' a certain architectural decision was made."""
    sync_tool = AIContextSync(config_path=config)
    from ...reasoning import DecisionReasoner

    reasoner = DecisionReasoner(sync_tool.llm_client, sync_tool.config.settings.adr_dir)
    explanation = reasoner.explain_decision(query)
    typer.echo(f"\n--- Decision Explanation ---\n{explanation}\n--------------------------\n")
