"""Sync and guard commands for AI-Context-Sync CLI."""
import subprocess
import sys

import typer

from ...core import AIContextSync
from .. import cli_error_handler


@cli_error_handler
def sync(
    config: str = typer.Option(".ai-sync.json", help="Path to config file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate sync without writing files"),
    detach: bool = typer.Option(False, "--detach", help="Run synchronization in background (detached process)")
) -> None:
    """Synchronize project context with the last git commit."""
    if detach:
        python_exe = sys.executable
        cmd = [python_exe, "-m", "src.cli", "sync", "--config", config]
        if dry_run:
            cmd.append("--dry-run")

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
        typer.echo("🕒 Sync triggered in background. You can continue working!")
        return

    sync_tool = AIContextSync(config_path=config, dry_run=dry_run)
    sync_tool.sync()


@cli_error_handler
def guard(
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
) -> None:
    """Audit current changes against established ADRs to detect architectural drift."""
    from ...config import AppConfig
    app_config = AppConfig.load(config)

    sync_tool = AIContextSync(config_path=config)
    diff = sync_tool.analyzer.get_last_commit_diff()
    commit_msg = sync_tool.analyzer.get_last_commit_message()
    filtered_diff = sync_tool.analyzer.filter_diff(diff)

    violations = sync_tool.guard.check_drift_json(filtered_diff, commit_msg)

    active_violations = [v for v in violations if v["rule_id"] not in app_config.settings.overridden_violations]

    if not active_violations:
        typer.echo("✅ All architectural aspects are compliant.")
    else:
        typer.echo("\n❌ Architectural Drift Detected:")
        for v in active_violations:
            typer.echo(f"  - [{v['rule_id']}] ({v['severity']}): {v['description']}")
        typer.echo("\n(Use 'dx override <rule_id>' to ignore specific violations.)")
