"""ADG - AI Developer Governance CLI (package).

公共符号采用 PEP 562 模块级 __getattr__ 懒加载: `adg --help` 只需要 parser,
不必为打印帮助而导入 18 个子命令与规则引擎。直接 `from ... import name` 的
调用方不受影响 (首次访问时解析并缓存到模块 globals)。
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_GROUPS: dict[str, tuple[str, ...]] = {
    "tools.scripts.adg_cli.check": (
        "_check_files_parallel",
        "_check_pattern",
        "_collect_check_files",
        "_get_git_changed_files",
        "_get_staged_files",
        "_get_unstaged_files",
        "_match_pattern",
        "check_directory",
        "check_file",
    ),
    "tools.scripts.adg_cli.core": (
        "_DEFAULT_PRE_COMMIT_HOOK",
        "_DEFAULT_PRE_PUSH_HOOK",
        "FIX_RULES",
        "SKIP_DIRS",
        "SKIP_DIRS_ALL",
        "SKIP_EXTENSIONS",
        "Issue",
        "_attach_docs_to_issues",
        "_get_rules_path",
        "_make_issue",
        "_merge_config",
        "_severity_rank",
        "load_project_config",
    ),
    "tools.scripts.adg_cli.detect": (
        "_detect_framework",
        "_detect_language_from_file",
        "_load_yaml",
        "_simple_yaml_parse",
        "detect_language",
    ),
    "tools.scripts.adg_cli.fix": ("_apply_fix", "fix_directory", "fix_file"),
    "tools.scripts.adg_cli.format": (
        "_count_issues",
        "_format_human",
        "_format_json",
        "_format_sarif",
        "_print_report_text",
    ),
    "tools.scripts.adg_cli.notify": (
        "_send_dingtalk_notification",
        "_send_slack_notification",
    ),
    "tools.scripts.adg_cli.parser": ("_build_parser",),
    "tools.scripts.adg_cli.rule_author": (
        "_RULE_TEMPLATE",
        "_create_rule_interactive",
        "_test_rule",
        "_validate_rule",
    ),
    "tools.scripts.adg_cli.rules": ("load_framework_rules", "load_rules_for_language"),
    "tools.scripts.adg_cli.trend": (
        "_TREND_DATA_FILE",
        "_format_trend_report",
        "_load_trend_data",
        "_record_trend",
        "_save_trend_data",
    ),
}

_COMMANDS: tuple[str, ...] = (
    "bench",
    "check",
    "cicd",
    "dashboard",
    "detect",
    "fix",
    "html-report",
    "install-hooks",
    "list-rules",
    "lsp",
    "marketplace",
    "monorepo",
    "notify",
    "pattern-learner",
    "recommend",
    "report",
    "rule",
    "trend",
)

_LAZY: dict[str, tuple[str, str]] = {
    name: (module_name, name) for module_name, names in _LAZY_GROUPS.items() for name in names
}
for _command in _COMMANDS:
    _attribute = f"cmd_{_command.replace('-', '_')}"
    _LAZY[_attribute] = (
        f"tools.scripts.adg_cli.commands.cmd.cmd_{_command.replace('-', '_')}",
        _attribute,
    )


def __getattr__(name: str) -> Any:
    """Resolve public API symbols on first access (PEP 562)."""
    try:
        module_name, attribute = _LAZY[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


def main() -> int:
    """CLI entry point. Only the selected subcommand is imported."""
    parser = importlib.import_module("tools.scripts.adg_cli.parser")._build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    from tools.scripts.adg_cli.commands import get_command_handler

    command = get_command_handler(args.command)
    return int(command(args))


__all__ = [
    # Core
    "Issue",
    "FIX_RULES",
    "SKIP_DIRS",
    "SKIP_DIRS_ALL",
    "SKIP_EXTENSIONS",
    "load_project_config",
    "load_rules_for_language",
    "load_framework_rules",
    # Check
    "check_directory",
    "check_file",
    "_check_files_parallel",
    "_check_pattern",
    "_collect_check_files",
    "_get_git_changed_files",
    "_get_staged_files",
    "_get_unstaged_files",
    "_match_pattern",
    # Detect
    "detect_language",
    "_detect_framework",
    "_detect_language_from_file",
    "_load_yaml",
    "_simple_yaml_parse",
    # Fix
    "fix_directory",
    "fix_file",
    "_apply_fix",
    # Format
    "_count_issues",
    "_format_human",
    "_format_json",
    "_format_sarif",
    "_print_report_text",
    # Core helpers
    "_attach_docs_to_issues",
    "_get_rules_path",
    "_make_issue",
    "_merge_config",
    "_severity_rank",
    "_DEFAULT_PRE_COMMIT_HOOK",
    "_DEFAULT_PRE_PUSH_HOOK",
    # Notify
    "_send_dingtalk_notification",
    "_send_slack_notification",
    # Rule author
    "_RULE_TEMPLATE",
    "_create_rule_interactive",
    "_test_rule",
    "_validate_rule",
    # Trend
    "_TREND_DATA_FILE",
    "_format_trend_report",
    "_load_trend_data",
    "_record_trend",
    "_save_trend_data",
    # Parser
    "_build_parser",
    # Commands
    "cmd_bench",
    "cmd_check",
    "cmd_cicd",
    "cmd_dashboard",
    "cmd_detect",
    "cmd_fix",
    "cmd_html_report",
    "cmd_install_hooks",
    "cmd_list_rules",
    "cmd_lsp",
    "cmd_marketplace",
    "cmd_monorepo",
    "cmd_notify",
    "cmd_pattern_learner",
    "cmd_recommend",
    "cmd_report",
    "cmd_rule",
    "cmd_trend",
    # CLI entry
    "main",
]
