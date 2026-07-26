"""ADG - AI Developer Governance CLI (package)."""

from tools.scripts.adg_cli.check import (
    _check_files_parallel,
    _check_pattern,
    _collect_check_files,
    _match_pattern,
    check_directory,
    check_file,
)
from tools.scripts.adg_cli.commands import (
    cmd_bench,
    cmd_check,
    cmd_cicd,
    cmd_dashboard,
    cmd_detect,
    cmd_fix,
    cmd_html_report,
    cmd_install_hooks,
    cmd_list_rules,
    cmd_lsp,
    cmd_marketplace,
    cmd_monorepo,
    cmd_notify,
    cmd_recommend,
    cmd_report,
    cmd_rule,
    cmd_trend,
)
from tools.scripts.adg_cli.core import (
    _ADG_HOME,
    _ADG_SOURCE,
    _DEFAULT_PRE_COMMIT_HOOK,
    _DEFAULT_PRE_PUSH_HOOK,
    _RULES_PATH,
    FIX_RULES,
    MAX_FILES,
    SKIP_DIRS,
    SKIP_EXTENSIONS,
    Issue,
    _get_rules_path,
    _make_issue,
    _merge_config,
    _severity_rank,
    load_project_config,
)
from tools.scripts.adg_cli.detect import (
    CONFIG_MARKERS,
    EXTENSION_MAP,
    FRAMEWORK_SIGNATURES,
    _detect_framework,
    _detect_language_from_file,
    _load_yaml,
    _simple_yaml_parse,
    detect_language,
)
from tools.scripts.adg_cli.fix import _apply_fix, fix_directory, fix_file
from tools.scripts.adg_cli.format import (
    _SEVERITY_COLORS,
    _count_issues,
    _format_human,
    _format_json,
    _format_sarif,
    _print_report_text,
)
from tools.scripts.adg_cli.git import (
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
)
from tools.scripts.adg_cli.notify import _send_dingtalk_notification, _send_slack_notification
from tools.scripts.adg_cli.parser import _build_parser
from tools.scripts.adg_cli.rule_author import (
    _create_rule_interactive,
    _test_rule,
    _validate_rule,
)
from tools.scripts.adg_cli.rules import load_framework_rules, load_rules_for_language
from tools.scripts.adg_cli.trend import (
    _TREND_DATA_FILE,
    _format_trend_report,
    _load_trend_data,
    _record_trend,
    _save_trend_data,
)


def main() -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    commands = {
        "check": cmd_check,
        "detect": cmd_detect,
        "list-rules": cmd_list_rules,
        "install-hooks": cmd_install_hooks,
        "report": cmd_report,
        "fix": cmd_fix,
        "rule": cmd_rule,
        "trend": cmd_trend,
        "notify": cmd_notify,
        "html-report": cmd_html_report,
        "recommend": cmd_recommend,
        "lsp": cmd_lsp,
        "dashboard": cmd_dashboard,
        "marketplace": cmd_marketplace,
        "monorepo": cmd_monorepo,
        "bench": cmd_bench,
        "cicd": cmd_cicd,
    }
    return commands[args.command](args)


__all__ = [name for name in dir() if not name.startswith("_")]
