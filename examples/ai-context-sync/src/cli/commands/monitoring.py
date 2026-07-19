"""Monitoring commands for AI-Context-Sync CLI."""
import os
import typer
from ...core import AIContextSync
from ...watcher import WatchManager
from .. import cli_error_handler


def _validate_file_path(path: str) -> bool:
    """
    Validate that a file path is safe to write to.
    
    Rejects:
    - Absolute paths
    - Paths with '..' (parent directory traversal)
    - Paths outside the current working directory
    - Empty or whitespace-only paths
    
    Returns True if path is safe, False otherwise.
    """
    if not path or not path.strip():
        return False
    
    # Reject absolute paths
    if os.path.isabs(path):
        return False
    
    # Reject paths with '..' (parent directory traversal)
    if ".." in path:
        return False
    
    # Reject paths that start with '~' (home directory)
    if path.startswith("~"):
        return False
    
    # Normalize the path and check if it's within the current directory
    try:
        normalized = os.path.normpath(path)
        # Get the current working directory
        cwd = os.getcwd()
        # Resolve the full path
        full_path = os.path.abspath(os.path.join(cwd, normalized))
        # Check if the resolved path is within the current directory
        if not full_path.startswith(cwd):
            return False
    except (OSError, ValueError):
        return False
    
    return True


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
    config: str = typer.Option(".ai-sync.json", help="Path to config file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying")
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

    if not _validate_file_path(target_file):
        typer.echo(f"❌ Rejected unsafe file path: {target_file}")
        return

    violations = sync_tool.auditor.audit(diff, "Applying fix")
    target_violation = next((v for v in violations if v.rule_id == rule_id), None)

    if not target_violation:
        typer.echo(f"❌ No active violation found for rule {rule_id} in {target_file}.")
        return

    specs = sync_tool.auditor.get_relevant_specs(diff)
    fix_code = sync_tool.auditor.generate_fix(target_violation, diff, specs)

    if dry_run:
        typer.echo(f"🔍 [Dry-run] Would apply fix for {rule_id} to {target_file}:")
        typer.echo(f"---\n{fix_code}\n---")
        return

    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(fix_code)
        typer.echo(f"✅ Successfully applied fix for {rule_id} to {target_file}.")
    except OSError as e:
        typer.echo(f"❌ Failed to write to {target_file}: {e}")
        raise typer.Exit(1)
