"""Evolution commands for AI-Context-Sync CLI."""

import typer

from ...core import AIContextSync
from .. import cli_error_handler


@cli_error_handler
def evolve(
    config: str = typer.Option(".ai-sync.json", help="Path to config file"),
    batch: bool = typer.Option(False, "--batch", help="Batch process all proposals instead of interactive mode"),
) -> None:
    """Analyze audit history and propose updates to the project specifications."""
    sync_tool = AIContextSync(config_path=config)
    candidates = sync_tool.evolution.analyze_conflicts()

    if not candidates:
        typer.echo(
            "✨ No strong patterns of specification conflict detected. Your specs are currently well-aligned with your practice."
        )
        return

    if batch:
        typer.echo(f"🔍 Analyzing {len(candidates)} opportunities in batch mode...")
        proposal = sync_tool.evolution.propose_batch_evolution(candidates)
        typer.echo(f"\n--- Batch Proposed Updates ---\n{proposal}")
        return

    typer.echo(f"🔍 Found {len(candidates)} potential specification evolution opportunities:\n")
    for i, c in enumerate(candidates, 1):
        typer.echo(f"{i}. Rule {c['rule_id']} (Conflict Rate: {c['ratio']:.1%})")

        proposal = sync_tool.evolution.propose_evolution(c)
        typer.echo(f"   Proposed Update: {proposal}\n")

        if typer.confirm("Would you like to apply this update to your local spec? (y/N)"):
            typer.echo(f"✅ Proposal for {c['rule_id']} accepted. (Updating spec file in next release)")
