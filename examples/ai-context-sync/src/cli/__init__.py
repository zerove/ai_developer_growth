"""AI-Context-Sync CLI - Modular Architecture.

Commands are organized into separate modules under cli/commands/:
- sync_guard.py: sync, guard commands
- audit.py: audit command
- analysis.py: trace, map, why commands
- evolution.py: evolve command
- monitoring.py: watch, apply_fix commands
- tools.py: scaffold, init, override, onboard, install_hook, report commands
- flow.py: flow command
"""
import functools
import typer
from typing import Any
from ..exceptions import AISyncError
from ..logger import logger

app = typer.Typer(help="AI-Context-Sync: Automate project context maintenance.")


def cli_error_handler(func: Any) -> Any:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise
        except AISyncError as e:
            logger.error(f"❌ {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            raise typer.Exit(code=1)
    return wrapper


# Import command functions from modules (each module exports raw functions)
from .commands.sync_guard import sync, guard
from .commands.audit import audit
from .commands.analysis import trace, map as map_cmd, why
from .commands.evolution import evolve
from .commands.monitoring import watch, apply_fix
from .commands.tools import scaffold, init, override, onboard, install_hook, report
from .commands.flow import flow

# Register all commands as flat (no nested groups)
app.command("sync")(sync)
app.command("guard")(guard)
app.command("audit")(audit)
app.command("trace")(trace)
app.command("map")(map_cmd)
app.command("why")(why)
app.command("evolve")(evolve)
app.command("watch")(watch)
app.command("apply-fix")(apply_fix)
app.command("scaffold")(scaffold)
app.command("init")(init)
app.command("override")(override)
app.command("onboard")(onboard)
app.command("install-hook")(install_hook)
app.command("report")(report)
app.command("flow")(flow)

if __name__ == "__main__":
    app()
