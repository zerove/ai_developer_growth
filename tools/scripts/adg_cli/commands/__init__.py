"""adg_cli commands package facade (lazy).

18 个子命令模块此前在包导入时全部急切加载, 导致 `adg --help` 冷启动
需要编译/执行所有命令实现 (含 lsp/dashboard/pattern-learner 等重依赖)。
改为 PEP 562 模块级 __getattr__ 后, 只有真正被分发的子命令才会被导入,
同时保持 `from tools.scripts.adg_cli.commands import cmd_check` 的兼容性。
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

_LAZY: dict[str, tuple[str, str]] = {
    "_cmd_rule_create": (
        "tools.scripts.adg_cli.commands.cmd._cmd_rule_create",
        "_cmd_rule_create",
    ),
    "_cmd_rule_test": (
        "tools.scripts.adg_cli.commands.cmd._cmd_rule_test",
        "_cmd_rule_test",
    ),
    "_cmd_rule_validate": (
        "tools.scripts.adg_cli.commands.cmd._cmd_rule_validate",
        "_cmd_rule_validate",
    ),
}
for _command in (
    "bench",
    "check",
    "cicd",
    "dashboard",
    "detect",
    "fix",
    "html_report",
    "install_hooks",
    "list_rules",
    "lsp",
    "marketplace",
    "monorepo",
    "notify",
    "pattern_learner",
    "recommend",
    "report",
    "rule",
    "trend",
):
    _LAZY[f"cmd_{_command}"] = (
        f"tools.scripts.adg_cli.commands.cmd.cmd_{_command}",
        f"cmd_{_command}",
    )


def __getattr__(name: str) -> Any:
    """Resolve command callables on first access (PEP 562)."""
    try:
        module_name, attribute = _LAZY[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


def get_command_handler(command: str) -> Callable[..., Any]:
    """按子命令名解析 handler（'html-report' → cmd_html_report 函数）。

    `adg` CLI 的 dispatch 唯一入口：所有子命令统一经由此函数取 handler，
    禁止在 dispatch 处散落各自的子命令字符串解析逻辑。
    """
    normalized = command.replace("-", "_")
    module_name, attribute = _LAZY[f"cmd_{normalized}"]
    return getattr(importlib.import_module(module_name), attribute)


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = sorted([*list(_LAZY), "get_command_handler"])
