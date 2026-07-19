"""Audit command for AI-Context-Sync CLI."""
import json as json_mod

import typer

from ...core import AIContextSync
from .. import cli_error_handler


@cli_error_handler
def audit(
    config: str = typer.Option(".ai-sync.json", help="Path to config file"),
    strict: bool = typer.Option(False, "--strict", help="Exit with error if Critical violations are found"),
    format: str = typer.Option("text", help="Output format ('text' or 'json')")
) -> None:
    """Audit current changes against language-specific development specifications."""
    sync_tool = AIContextSync(config_path=config)

    # Single LLM call to get violations
    commit_msg = sync_tool.analyzer.get_last_commit_message()
    diff = sync_tool.analyzer.get_last_commit_diff()
    filtered_diff = sync_tool.analyzer.filter_diff(diff)

    if not filtered_diff:
        typer.echo("✨ No changes to audit.")
        return

    violations = sync_tool.auditor.audit(filtered_diff, commit_msg)

    # Filter out overridden violations
    active_violations = [v for v in violations if v.rule_id not in [
        item['rule_id'] for item in sync_tool.feedback.history if item['status'] == 'overridden'
    ]]

    # Save violations to feedback history
    for v in active_violations:
        sync_tool.feedback.save_violation(v)

    # Handle strict mode
    if strict:
        has_critical = any(v.severity == 'Critical' for v in active_violations)
        if has_critical:
            if format == "json":
                json_output = json_mod.dumps([v.to_dict() for v in active_violations], indent=2)
                typer.echo(json_output)
            else:
                typer.echo("\n❌ STRICT MODE: Critical specification violations detected. Commit blocked.")
                typer.echo("Please fix the issues or use 'dx override <rule_id>' to mark them as acceptable.")
            raise typer.Exit(code=1)

    # Output results
    if format == "json":
        typer.echo(json_mod.dumps([v.to_dict() for v in active_violations], indent=2))
    else:
        if not active_violations:
            typer.echo("✅ All changes comply with specifications.")
        else:
            report = [f"Found {len(active_violations)} violation(s):"]
            for i, v in enumerate(active_violations, 1):
                report.append(f"{i}. [{v.severity}] {v.rule_id}: {v.message}")
            typer.echo(f"\n--- Language Spec Audit Report ---\n{chr(10).join(report)}\n---------------------------------\n")
