from __future__ import annotations

import argparse
from typing import Any


def _add_base_check_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'check' subcommand parser."""
    check_p = sub.add_parser("check", help="Check code against rules")
    check_p.add_argument("path", help="File or directory to check")
    check_p.add_argument("--lang", help="Force language (skip auto-detection)")
    check_p.add_argument("--framework", help="Force framework (skip auto-detection)")
    check_p.add_argument(
        "--severity", choices=["error", "warning", "info"], help="Only show issues at this severity or higher"
    )
    check_p.add_argument("--json", action="store_true", help="Output as JSON")
    check_p.add_argument("--sarif", action="store_true", help="Output as SARIF (GitHub Code Scanning)")
    check_p.add_argument("-j", "--jobs", type=int, default=1, help="Number of parallel jobs (default: 1)")
    check_p.add_argument(
        "--since", type=str, default=None, help="Only check files changed since git ref (e.g., HEAD~1, main)"
    )
    check_p.add_argument("--staged", action="store_true", help="Only check staged files (for pre-commit)")
    check_p.add_argument("--unstaged", action="store_true", help="Only check unstaged changed files")
    check_p.add_argument("--trend", action="store_true", help="Record results for trend tracking")
    check_p.add_argument(
        "--notify", type=str, default=None, help="Send results to webhook (slack://... or dingtalk://...)"
    )
    check_p.add_argument("--with-docs", action="store_true", help="Include related documentation links in output")


def _add_detect_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'detect' subcommand parser."""
    detect_p = sub.add_parser("detect", help="Detect project language/framework")
    detect_p.add_argument("path", nargs="?", default=".", help="Project directory")
    detect_p.add_argument("--json", action="store_true", help="Output as JSON")


def _add_list_rules_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'list-rules' subcommand parser."""
    list_p = sub.add_parser("list-rules", help="List rules for a language")
    list_p.add_argument("--lang", required=True, help="Language name")
    list_p.add_argument("--json", action="store_true", help="Output as JSON")


def _add_install_hooks_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'install-hooks' subcommand parser."""
    install_p = sub.add_parser("install-hooks", help="Install pre-commit/pre-push hook")
    install_p.add_argument("path", nargs="?", default=".", help="Project directory")
    install_p.add_argument("--pre-push", action="store_true", help="Install pre-push hook instead of pre-commit")


def _add_report_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'report' subcommand parser."""
    report_p = sub.add_parser("report", help="Generate quality gate report")
    report_p.add_argument("path", help="File or directory to report on")
    report_p.add_argument("--lang", help="Force language (skip auto-detection)")
    report_p.add_argument("--framework", help="Force framework (skip auto-detection)")
    report_p.add_argument("--error-threshold", type=int, default=0, help="Max errors allowed (default: 0)")
    report_p.add_argument("--warning-threshold", type=int, default=-1, help="Max warnings allowed (-1 = no limit)")
    report_p.add_argument("--json", action="store_true", help="Output as JSON")


def _add_fix_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'fix' subcommand parser."""
    fix_p = sub.add_parser("fix", help="Apply automatic fixes to code")
    fix_p.add_argument("path", help="File or directory to fix")
    fix_p.add_argument("--lang", help="Force language (skip auto-detection)")
    fix_p.add_argument("--json", action="store_true", help="Output as JSON")


def _add_rule_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'rule' subcommand parser with subcommands."""
    rule_p = sub.add_parser("rule", help="Create/test governance rules")
    rule_sub = rule_p.add_subparsers(dest="rule_command")
    rule_create = rule_sub.add_parser("create", help="Create a new rule interactively")
    rule_create.add_argument("--output", type=str, help="Output YAML file path")
    rule_test = rule_sub.add_parser("test", help="Test a rule against files")
    rule_test.add_argument("rule-file", type=str, help="Rule YAML file to test")
    rule_test.add_argument("path", type=str, help="Files/directory to test against")
    rule_validate = rule_sub.add_parser("validate", help="Validate a rule file")
    rule_validate.add_argument("rule-file", type=str, help="Rule YAML file to validate")


def _add_trend_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'trend' subcommand parser."""
    trend_p = sub.add_parser("trend", help="Show quality trend dashboard")
    trend_p.add_argument("path", nargs="?", default=".", help="Project directory")
    trend_p.add_argument("--json", action="store_true", help="Output as JSON")
    trend_p.add_argument("--clear", action="store_true", help="Clear trend history")


def _add_notify_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'notify' subcommand parser."""
    notify_p = sub.add_parser("notify", help="Send governance report via webhook")
    notify_p.add_argument("path", help="File or directory to check")
    notify_p.add_argument("--webhook", required=True, help="Webhook URL (slack://... or dingtalk://...)")
    notify_p.add_argument("--lang", help="Force language")
    notify_p.add_argument("--project", type=str, default=".", help="Project name")


def _add_html_report_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'html-report' subcommand parser."""
    html_p = sub.add_parser("html-report", help="Generate beautiful HTML quality gate report")
    html_p.add_argument("path", help="File or directory to report on")
    html_p.add_argument("-o", "--output", default="adg-report.html", help="Output HTML file (default: adg-report.html)")
    html_p.add_argument("--lang", help="Force language")


def _add_recommend_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'recommend' subcommand parser."""
    recommend_p = sub.add_parser("recommend", help="AI-powered rule recommendations for codebase")
    recommend_p.add_argument("path", nargs="?", default=".", help="Project directory")
    recommend_p.add_argument("--json", action="store_true", help="Output as JSON")
    recommend_p.add_argument("-n", "--max", type=int, default=20, help="Max recommendations")
    recommend_p.add_argument("--apply", action="store_true", help="Auto-generate .adg/rules.yml with recommended rules")


def _add_lsp_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'lsp' subcommand parser."""
    lsp_p = sub.add_parser("lsp", help="Start ADG Language Server (LSP)")
    lsp_p.add_argument("--stdio", action="store_true", help="Use stdio transport")
    lsp_p.add_argument("--port", type=int, default=8080, help="TCP port")
    lsp_p.add_argument("--log-level", default="INFO", help="Log level")


def _add_dashboard_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'dashboard' subcommand parser."""
    dash_p = sub.add_parser("dashboard", help="Start web dashboard or generate static HTML")
    dash_p.add_argument("path", nargs="?", default=".", help="Project directory")
    dash_p.add_argument("--port", type=int, default=8080, help="Server port")
    dash_p.add_argument("--static", help="Generate static HTML to file")
    dash_p.add_argument("--host", default="127.0.0.1", help="Server host")


def _add_marketplace_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'marketplace' subcommand parser."""
    mkt_p = sub.add_parser("marketplace", help="Rule pack marketplace")
    mkt_sub = mkt_p.add_subparsers(dest="marketplace_command")
    mkt_sub.add_parser("list", help="List available packs")
    mkt_search = mkt_sub.add_parser("search", help="Search packs")
    mkt_search.add_argument("query", help="Search query")
    mkt_install = mkt_sub.add_parser("install", help="Install a rule pack")
    mkt_install.add_argument("pack_id", help="Pack ID to install")
    mkt_install.add_argument("--lang", help="Target language only")
    mkt_uninstall = mkt_sub.add_parser("uninstall", help="Uninstall a rule pack")
    mkt_uninstall.add_argument("pack_id", help="Pack ID to uninstall")


def _add_monorepo_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'monorepo' subcommand parser."""
    mono_p = sub.add_parser("monorepo", help="Check all projects in a monorepo")
    mono_p.add_argument("path", nargs="?", default=".", help="Monorepo root directory")
    mono_p.add_argument("--json", action="store_true", help="Output as JSON")
    mono_p.add_argument("--lang", help="Force language for all projects")


def _add_bench_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'bench' subcommand parser."""
    bench_p = sub.add_parser("bench", help="Run performance benchmarks")
    bench_p.add_argument("--files", type=str, default="100,500", help="Comma-separated file counts")
    bench_p.add_argument("--languages", type=str, default="python,javascript", help="Comma-separated languages")
    bench_p.add_argument("-o", "--output", help="Output JSON file")


def _add_cicd_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'cicd' subcommand parser."""
    cicd_p = sub.add_parser("cicd", help="Generate CI/CD configuration files")
    cicd_p.add_argument(
        "platform", choices=["github", "github-advanced", "gitlab", "jenkins", "docker"], help="CI/CD platform"
    )
    cicd_p.add_argument("-o", "--output", default=".", help="Output directory")


def _add_pattern_learner_parser(sub: argparse._SubParsersAction[Any]) -> None:
    """Add 'pattern-learner' subcommand parser."""
    pl_p = sub.add_parser("pattern-learner", help="Learn team coding norms from codebase")
    pl_p.add_argument("path", nargs="?", default=".", help="Project directory")
    pl_p.add_argument("--json", action="store_true", help="Output as JSON")
    pl_p.add_argument("--min-occurrences", type=int, default=3, help="Minimum occurrences for pattern (default: 3)")


def _add_new_commands(sub: argparse._SubParsersAction[Any]) -> None:
    """Add new commands: HTML report, recommend, dashboard, marketplace, monorepo, bench, cicd, pattern-learner."""
    _add_html_report_parser(sub)
    _add_recommend_parser(sub)
    _add_lsp_parser(sub)
    _add_dashboard_parser(sub)
    _add_marketplace_parser(sub)
    _add_monorepo_parser(sub)
    _add_bench_parser(sub)
    _add_cicd_parser(sub)
    _add_pattern_learner_parser(sub)


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="adg",
        description="ADG - AI Developer Governance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # Core commands
    _add_base_check_parser(sub)
    _add_detect_parser(sub)
    _add_list_rules_parser(sub)
    _add_install_hooks_parser(sub)
    _add_report_parser(sub)
    _add_fix_parser(sub)
    _add_rule_parser(sub)
    _add_trend_parser(sub)
    _add_notify_parser(sub)

    # New commands
    _add_new_commands(sub)

    return parser
