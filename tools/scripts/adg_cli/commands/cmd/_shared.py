from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from tools.scripts.adg_cli.check import (
    _check_files_parallel,
    _check_python_complexity,
    _collect_check_files,
    _make_check_error_issue,
    check_directory,
    check_file,
)
from tools.scripts.adg_cli.core import (
    _DEFAULT_PRE_COMMIT_HOOK,
    _DEFAULT_PRE_PUSH_HOOK,
    SKIP_DIRS,
    SKIP_DIRS_ALL,
    SKIP_EXTENSIONS,
    Issue,
    _attach_docs_to_issues,
    load_project_config,
)
from tools.scripts.adg_cli.detect import _detect_language_from_file, detect_language
from tools.scripts.adg_cli.fix import fix_directory, fix_file
from tools.scripts.adg_cli.format import (
    _RESET,
    _SEVERITY_COLORS,
    _count_issues,
    _format_human,
    _format_json,
    _format_sarif,
    _print_report_text,
)
from tools.scripts.adg_cli.notify import (
    _send_dingtalk_notification,
    _send_slack_notification,
)
from tools.scripts.adg_cli.rule_author import (
    _RULE_TEMPLATE,
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
)

__all__ = [
    "Path",
    "Any",
    "_check_files_parallel",
    "_check_python_complexity",
    "_collect_check_files",
    "_make_check_error_issue",
    "check_directory",
    "check_file",
    "_DEFAULT_PRE_COMMIT_HOOK",
    "_DEFAULT_PRE_PUSH_HOOK",
    "SKIP_DIRS",
    "SKIP_DIRS_ALL",
    "SKIP_EXTENSIONS",
    "Issue",
    "_attach_docs_to_issues",
    "load_project_config",
    "_detect_language_from_file",
    "detect_language",
    "fix_directory",
    "fix_file",
    "_RESET",
    "_SEVERITY_COLORS",
    "_count_issues",
    "_format_human",
    "_format_json",
    "_format_sarif",
    "_print_report_text",
    "_send_dingtalk_notification",
    "_send_slack_notification",
    "_RULE_TEMPLATE",
    "_create_rule_interactive",
    "_test_rule",
    "_validate_rule",
    "load_framework_rules",
    "load_rules_for_language",
    "_TREND_DATA_FILE",
    "_format_trend_report",
    "_load_trend_data",
    "_record_trend",
    "_load_rule_from_yaml",
    "_load_rules_from_file",
    "_collect_test_files",
    "_print_test_results",
    "_expand_rule_set",
]


def _load_rule_from_yaml(rule_file: Path) -> dict[str, Any]:
    """Load rule from YAML file, with fallback parsing."""
    try:
        import yaml

        with open(rule_file) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except ImportError:
        # Fallback: try simple parsing
        content = rule_file.read_text()
        rule_data = {"pattern": "", "message": ""}
        for line in content.split("\n"):
            if "pattern:" in line:
                rule_data["pattern"] = line.split("pattern:")[1].strip().strip('"')
            elif "message:" in line:
                rule_data["message"] = line.split("message:")[1].strip().strip('"')
        return rule_data


def _collect_test_files(target: Path) -> list[Path]:
    """Collect test files from target path."""
    if target.is_file():
        return [target]

    test_files = []
    for fp in target.rglob("*"):
        if fp.is_file() and fp.suffix in (".py", ".js", ".ts", ".go", ".rs", ".java"):
            test_files.append(fp)
    return test_files


def _print_test_results(results: dict[str, Any]) -> None:
    """Print test results."""
    print(f"\nRule: {results['rule_id']}")
    print(f"Files tested: {results['files_tested']}")
    print(f"Matches found: {len(results['matches'])}")

    if results["matches"]:
        print("\nMatches:")
        for match in results["matches"][:20]:  # Limit to 20
            print(f"  {match['file']}:{match['line']}: {match['match']}")

    if results["errors"]:
        print("\nErrors:")
        for e in results["errors"]:
            print(f"  - {e}")


def _parse_rule_file_simple(content: str) -> dict[str, Any]:
    """无 yaml 时的极简解析 (Phase 36c cc 拆分: 从 _load_rules_from_file 抽出)."""
    data: dict[str, Any] = {}
    for line in content.split("\n"):
        if "pattern:" in line:
            data["pattern"] = line.split("pattern:")[1].strip().strip('"')
        elif "message:" in line:
            data["message"] = line.split("message:")[1].strip().strip('"')
        elif "severity:" in line:
            data["severity"] = line.split("severity:")[1].strip()
        elif "category:" in line:
            data["category"] = line.split("category:")[1].strip()
        elif "id:" in line and not line.strip().startswith("#"):
            data["id"] = line.split("id:")[1].strip()
    return data


def _load_rules_from_file(rule_file: Path) -> object:
    """Load rules from YAML file, fallback to simple parsing without yaml."""
    try:
        import yaml

        with open(rule_file) as f:
            return yaml.safe_load(f)
    except ImportError:
        return _parse_rule_file_simple(rule_file.read_text())


def _expand_rule_set(data: object) -> list[tuple[str, dict[str, Any]]]:
    """展开规则集合为 (标签, 规则) 列表；单规则 dict 返回单项。"""
    if isinstance(data, list):
        return [(f"#{i + 1}", r) for i, r in enumerate(data) if isinstance(r, dict)]
    if isinstance(data, dict) and isinstance(data.get("anti_patterns"), list):
        return [(str(r.get("id", f"#{i + 1}")), r) for i, r in enumerate(data["anti_patterns"]) if isinstance(r, dict)]
    if isinstance(data, dict):
        return [("rule", data)]
    return []
