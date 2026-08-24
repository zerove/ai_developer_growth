"""Flow command for AI-Context-Sync CLI."""

import os

import typer

from ...core import AIContextSync
from ...logger import logger
from .. import cli_error_handler


@cli_error_handler
def flow(task: str, config: str = typer.Option(".ai-sync.json", help="Path to config file")) -> None:
    """Execute the full AI-Native development flow for a specific task."""
    sync_tool = AIContextSync(config_path=config)

    logger.info("🔍 Phase 1: Sensing hierarchical context...")
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
        confirm = typer.confirm("Do you approve this design? (y/N)")
        return confirm

    result = sync_tool.orchestrator.run_flow(task, approval_callback, initial_context=aggregated_context)
    typer.echo(f"\n--- Workflow Result ---\n{result}\n----------------------\n")
