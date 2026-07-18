"""Tool commands for AI-Context-Sync CLI."""
import os
import shutil
import subprocess
import typer
from ...core import AIContextSync
from ...logger import logger
from .. import cli_error_handler

app = typer.Typer()


@app.command()
def scaffold(
    template: str = typer.Argument(..., help="Template name (in templates/ directory)"),
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
) -> None:
    """Initialize a project from a predefined template."""
    # 1. Check if directory is empty
    if len([f for f in os.listdir('.') if f not in ['.git', '.DS_Store']]) > 0:
        typer.echo("❌ Directory is not empty. Aborting.")
        raise typer.Exit(code=1)
    
    # 2. Check if template exists
    template_path = os.path.join("..", "..", "..", "templates", template)
    if not os.path.exists(template_path):
        typer.echo(f"❌ Template '{template}' not found in templates/.")
        raise typer.Exit(code=1)
    
    # 3. Copy files
    # Simplified copy logic for demonstration
    for item in os.listdir(template_path):
        src = os.path.join(template_path, item)
        if os.path.isdir(src):
            shutil.copytree(src, item)
        else:
            shutil.copy2(src, item)
            
    # 4. Init
    init(config=config)
    
    # 5. Update CONTEXT.md
    with open("CONTEXT.md", "a") as f:
        f.write(f"\n--- Initialized from template: {template} ---\n")
    typer.echo(f"✅ Successfully scaffolded from {template}")


@app.command()
def init(
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
) -> None:
    """Initialize a default .ai-sync.json configuration file."""
    if os.path.exists(config):
        logger.warning(f"Config file {config} already exists. Skipping.")
        return
    
    from ...config import AppConfig
    default_config = AppConfig()
    with open(config, "w") as f:
        import json
        def d_to_dict(obj):
            if hasattr(obj, "__dict__"):
                return {k: d_to_dict(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [d_to_dict(i) for i in obj]
            return obj
        json.dump(d_to_dict(default_config), f, indent=2)
    logger.info(f"✅ Initialized default config at {config}")


@app.command()
@cli_error_handler
def override(
    rule_id: str,
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
) -> None:
    """Mark a specification violation as overridden."""
    from ...config import AppConfig
    app_config = AppConfig.load(config)
    
    if rule_id not in app_config.settings.overridden_violations:
        app_config.settings.overridden_violations.append(rule_id)
        app_config.save()
        typer.echo(f"✅ Rule '{rule_id}' has been overridden.")
    else:
        typer.echo(f"ℹ️ Rule '{rule_id}' is already overridden.")


@app.command()
@cli_error_handler
def onboard(
    config: str = typer.Option(".ai-sync.json", help="Path to config file")
) -> None:
    """Start an interactive architecture onboarding tour."""
    sync_tool = AIContextSync(config_path=config)
    from ...onboarding import OnboardingSession
    session = OnboardingSession(sync_tool.llm_client)
    session.start()


HOOK_TEMPLATE = """#!/bin/bash
# AI-Context-Sync pre-commit hook
# Installed by: dx install-hook

echo "🔍 Running AI-Context-Sync audit..."

python -m ai_developer_growth.products.ai_context_sync.src.cli audit --strict --config .ai-sync.json

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ AI-Context-Sync audit failed. Commit blocked."
    echo "   Fix violations or use 'dx override <rule_id>' to suppress."
    exit 1
fi

echo "✅ AI-Context-Sync audit passed."
exit 0
"""


@app.command()
@cli_error_handler
def install_hook() -> None:
    """Install a Git pre-commit hook for automatic audit."""
    git_dir = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, text=True, check=True
    ).stdout.strip()

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    hook_path = os.path.join(hooks_dir, "pre-commit")

    if os.path.exists(hook_path):
        with open(hook_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if "AI-Context-Sync" in existing:
            typer.echo("ℹ️ AI-Context-Sync hook already installed.")
            return
        backup = hook_path + ".backup"
        shutil.copy2(hook_path, backup)
        typer.echo(f"📦 Existing hook backed up to {backup}")

    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(HOOK_TEMPLATE)
    os.chmod(hook_path, 0o755)

    typer.echo("✅ AI-Context-Sync pre-commit hook installed.")
    typer.echo("   Commits will now run 'dx audit --strict' automatically.")


@app.command()
@cli_error_handler
def report(
    output: str = typer.Option("docs/audit-report.html", help="Output HTML file path"),
    config: str = typer.Option(".ai-sync.json", help="Path to config file"),
) -> None:
    """Generate an HTML audit report for visualization."""
    sync_tool = AIContextSync(config_path=config)
    violations = sync_tool.auditor.audit(
        sync_tool.analyzer.get_last_commit_diff(),
        sync_tool.analyzer.get_last_commit_message()
    )
    violation_dicts = [v.to_dict() for v in violations]

    from ...report import generate_html_report, save_report
    html_content = generate_html_report(violation_dicts)
    saved_path = save_report(html_content, output)
    typer.echo(f"✅ Audit report generated: {saved_path}")
    typer.echo(f"   {len(violation_dicts)} violations found.")
