"""AI-Context-Sync CLI - Modular Architecture.

Commands are organized into separate modules under cli/commands/:
- sync_guard.py: sync, guard commands
- audit.py: audit command
- analysis.py: trace, map, why commands
- evolution.py: evolve command
- monitoring.py: watch, apply_fix commands
- tools.py: scaffold, init, override, onboard, install_hook, report commands
- flow.py: flow command

共享的 app 实例与错误处理装饰器放在 ``cli/_base.py``: 本模块要导入命令模块
完成注册, 命令模块又要用错误处理装饰器, 若装饰器留在本模块就成环
(``cli/__init__.py → cli/commands/*.py → cli/__init__.py``)。
"""

import typer

from ._base import cli_error_handler

app = typer.Typer(help="AI-Context-Sync: Automate project context maintenance.")

__all__ = ["app", "cli_error_handler"]


# Import command functions from modules (each module exports raw functions)
from .commands.analysis import map as map_cmd  # noqa: E402
from .commands.analysis import trace, why  # noqa: E402
from .commands.audit import audit  # noqa: E402
from .commands.evolution import evolve  # noqa: E402
from .commands.flow import flow  # noqa: E402
from .commands.monitoring import apply_fix, watch  # noqa: E402
from .commands.sync_guard import guard, sync  # noqa: E402
from .commands.tools import (  # noqa: E402
    init,
    install_hook,
    onboard,
    override,
    report,
    scaffold,
)

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
