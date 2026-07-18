"""Monitoring commands for AI-Context-Sync CLI."""
import os
import typer
from ...core import AIContextSync
from ...watcher import WatchManager
from .. import cli_error_handler


@cli_error_handler
def watch(
    config: str = typer.Option(".ai-sync.json", help="Path to config file"),
    path: str = typer.Option(".", help="Path to watch")
) -> None:
    """Start the real-time audit guard. Monitors file changes and updates the live report."""
    sync_tool = AIContextSync(config_path=config)
    watcher = WatchManager(sync_tool)
    watcher.start(path=path)


@cli_error_handler
def apply_fix(
    rule_id: str,
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
) -> None:
    """Automatically apply the suggested fix for a specific rule violation."""
    sync_tool = AIContextSync(config_path=config)

    diff = sync_tool.analyzer.get_last_commit_diff()
    target_file = "unknown"
    if diff:
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                target_file = line[6:]
                break

    if target_file == "unknown":
        typer.echo("❌ Could not identify the target file for the fix.")
        return

    violations = sync_tool.auditor.audit(diff, "Applying fix")
    target_violation = next((v for v in violations if v.rule_id == rule_id), None)

    if not target_violation:
        typer.echo(f"❌ No active violation found for rule {rule_id} in {target_file}.")
        return

    specs = sync_tool.auditor._get_relevant_specs(diff)
    fix_code = sync_tool.auditor.generate_fix(target_violation, diff, specs)

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(fix_code)

    typer.echo(f"✅ Successfully applied fix for {rule_id} to {target_file}.")
