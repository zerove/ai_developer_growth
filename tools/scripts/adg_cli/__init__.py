"""ADG - AI Developer Governance CLI (package)."""

from tools.scripts.adg_cli.core import (
    Issue,
    _get_rules_path,
    _ADG_HOME,
    _RULES_PATH,
    _ADG_SOURCE,
    load_project_config,
    _merge_config,
    _severity_rank,
    _make_issue,
    SKIP_DIRS,
    SKIP_EXTENSIONS,
    MAX_FILES,
    FIX_RULES,
    _DEFAULT_PRE_COMMIT_HOOK,
    _DEFAULT_PRE_PUSH_HOOK,
)
from tools.scripts.adg_cli.detect import (
    detect_language,
    _detect_framework,
    _detect_language_from_file,
    _load_yaml,
    _simple_yaml_parse,
    EXTENSION_MAP,
    CONFIG_MARKERS,
    FRAMEWORK_SIGNATURES,
)
from tools.scripts.adg_cli.rules import load_rules_for_language, load_framework_rules
from tools.scripts.adg_cli.check import (
    check_file,
    check_directory,
    _check_pattern,
    _check_files_parallel,
    _collect_check_files,
    _match_pattern,
)
from tools.scripts.adg_cli.fix import _apply_fix, fix_file, fix_directory
from tools.scripts.adg_cli.format import (
    _format_sarif,
    _format_human,
    _format_json,
    _count_issues,
    _print_report_text,
    _SEVERITY_COLORS,
)
from tools.scripts.adg_cli.git import (
    _get_git_changed_files,
    _get_unstaged_files,
    _get_staged_files,
)
from tools.scripts.adg_cli.trend import (
    _load_trend_data,
    _save_trend_data,
    _record_trend,
    _format_trend_report,
    _TREND_DATA_FILE,
)
from tools.scripts.adg_cli.notify import _send_slack_notification, _send_dingtalk_notification
from tools.scripts.adg_cli.rule_author import (
    _create_rule_interactive,
    _validate_rule,
    _test_rule,
)
from tools.scripts.adg_cli.commands import (
    cmd_check,
    cmd_detect,
    cmd_list_rules,
    cmd_install_hooks,
    cmd_report,
    cmd_fix,
    cmd_rule,
    cmd_trend,
    cmd_notify,
    cmd_html_report,
    cmd_recommend,
    cmd_lsp,
    cmd_dashboard,
    cmd_marketplace,
    cmd_monorepo,
    cmd_bench,
    cmd_cicd,
)
from tools.scripts.adg_cli.parser import _build_parser


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
