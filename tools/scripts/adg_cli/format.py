from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.core import Issue

_SEVERITY_COLORS = {"error": "\033[91m", "warning": "\033[93m", "info": "\033[96m"}
_RESET = "\033[0m"


def _format_human(issues: list[Issue], language: str, framework: str | None, files_checked: int) -> str:
    """Format issues as human-readable output (V2.21 P5-23 拆分: 抽 _format_issue_lines + _count_by_severity + _format_summary)."""
    lines: list[str] = []

    fw_str = f" + {framework}" if framework else ""
    lines.append(f"Language: {language}{fw_str} (auto-detected)")
    lines.append(f"Issues found: {len(issues)}")
    lines.append("")

    lines.extend(_format_issue_lines(issues))

    error_count, warning_count, info_count = _count_by_severity(issues)
    lines.append("")
    lines.append(_format_summary(error_count, warning_count, info_count, files_checked))
    return "\n".join(lines)


def _format_issue_lines(issues: list[Issue]) -> list[str]:
    """按 file/line 排序, 格式化为 issue 行 (模块级 helper).

    Args:
        issues: issue 列表

    Returns:
        格式化后的字符串行列表
    """
    lines: list[str] = []
    by_file: dict[str, list[Issue]] = {}
    for issue in issues:
        by_file.setdefault(issue.file, []).append(issue)

    for filepath, file_issues in sorted(by_file.items()):
        for issue in sorted(file_issues, key=lambda i: i.line):
            color = _SEVERITY_COLORS.get(issue.severity, "")
            loc = f"{issue.file}:{issue.line}:{issue.column}"
            lines.append(f"{loc}  {color}{issue.severity:7s}{_RESET}  {issue.rule_id:30s}  {issue.message}")
            if issue.fix_hint:
                lines.append(f"{' ' * len(loc)}  {' ' * 7}  {' ' * 30}  → {issue.fix_hint}")
    return lines


def _count_by_severity(issues: list[Issue]) -> tuple[int, int, int]:
    """按 severity 计数 (模块级 helper, 类似 P4-50 _compute_result_counts).

    Args:
        issues: issue 列表

    Returns:
        (error, warning, info) 三元组
    """
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")
    return error_count, warning_count, info_count


def _format_summary(error_count: int, warning_count: int, info_count: int, files_checked: int) -> str:
    """格式化汇总行 (模块级 helper).

    Args:
        error_count: error 数
        warning_count: warning 数
        info_count: info 数
        files_checked: 已检查文件数

    Returns:
        汇总字符串
    """
    parts = []
    if error_count:
        parts.append(f"\033[91m{error_count} error{'s' if error_count != 1 else ''}\033[0m")
    if warning_count:
        parts.append(f"\033[93m{warning_count} warning{'s' if warning_count != 1 else ''}\033[0m")
    if info_count:
        parts.append(f"\033[96m{info_count} info\033[0m")

    if parts:
        return f"{'  '.join(parts)} in {files_checked} file{'s' if files_checked != 1 else ''}"
    return f"\033[92m✓ All checks passed\033[0m ({files_checked} files)"


def _format_json(issues: list[Issue], language: str, framework: str | None, files_checked: int) -> str:
    """Format issues as JSON output."""
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    return json.dumps(
        {
            "language": language,
            "framework": framework,
            "files_checked": files_checked,
            "issues": [i.to_dict() for i in issues],
            "summary": {
                "error": error_count,
                "warning": warning_count,
                "info": info_count,
            },
        },
        indent=2,
        ensure_ascii=False,
    )


def _build_sarif_rules(issues: list[Issue], language: str) -> dict[str, dict[str, Any]]:
    """Build SARIF rules dictionary from issues."""
    rules = {}
    for issue in issues:
        if issue.rule_id not in rules:
            rules[issue.rule_id] = {
                "id": issue.rule_id,
                "shortDescription": {"text": issue.message},
                "fullDescription": {"text": issue.message},
                "helpUri": f"https://github.com/ai-developer-growth/rules/{issue.rule_id}",
                "properties": {
                    "category": issue.category,
                    "language": language,
                },
            }
    return rules


def _build_sarif_result(issue: Issue) -> dict[str, Any]:
    """Build a single SARIF result object from an issue."""
    level_map = {"error": "error", "warning": "warning", "info": "note"}
    level = level_map.get(issue.severity, "warning")

    result = {
        "ruleId": issue.rule_id,
        "level": level,
        "message": {"text": issue.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": issue.file},
                    "region": {
                        "startLine": issue.line,
                        "startColumn": issue.column,
                    },
                }
            }
        ],
        "fixes": [],
    }

    if issue.fix_hint:
        result["fixes"] = [
            {
                "description": {"text": issue.fix_hint},
                "artifactChanges": [
                    {
                        "artifactLocation": {"uri": issue.file},
                        "replacements": [
                            {
                                "deletedRegion": {
                                    "startLine": issue.line,
                                    "startColumn": issue.column,
                                },
                                "insertedContent": {"text": issue.fix_hint},
                            }
                        ],
                    }
                ],
            }
        ]

    return result


def _format_sarif(issues: list[Issue], language: str, framework: str | None) -> str:
    """Format issues as SARIF 2.1.0 for GitHub Code Scanning."""
    rules = _build_sarif_rules(issues, language)
    results = [_build_sarif_result(issue) for issue in issues]

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "adg",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/ai-developer-growth/adg",
                        "rules": list(rules.values()),
                    },
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif, indent=2)


def _count_issues(
    all_issues: list[Issue],
) -> tuple[dict[str, int], dict[str, int], list[tuple[str, int]]]:
    """Count issues by severity, category, and file. Returns (severity_counts, category_counts, top_files)."""
    severity_counts: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for issue in all_issues:
        if issue.severity in severity_counts:
            severity_counts[issue.severity] += 1

    category_counts: dict[str, int] = {}
    for issue in all_issues:
        cat = issue.category or "unknown"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    file_counts: dict[str, int] = {}
    for issue in all_issues:
        file_counts[issue.file] = file_counts.get(issue.file, 0) + 1

    top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return severity_counts, category_counts, top_files


def _print_report_text(
    target: Path,
    language: str,
    framework: str | None,
    files_checked: int,
    severity_counts: dict[str, int],
    category_counts: dict[str, int],
    top_files: list[tuple[str, int]],
    passed: bool,
    error_threshold: int,
    warning_threshold: int,
) -> None:
    """Print the human-readable quality gate report."""
    green = "\033[0;32m"
    red = "\033[0;31m"
    yellow = "\033[0;33m"
    cyan = "\033[0;36m"
    bold = "\033[1m"
    nc = "\033[0m"

    print(f"\n{bold}{cyan}{'=' * 60}{nc}")
    print(f"{bold}{cyan}  ADG Quality Gate Report{nc}")
    print(f"{bold}{cyan}{'=' * 60}{nc}\n")

    print(f"{bold}Project:{nc} {target}")
    print(f"{bold}Language:{nc} {language}" + (f" + {framework}" if framework else ""))
    print(f"{bold}Files Checked:{nc} {files_checked}")
    print()

    print(f"{bold}Issues by Severity:{nc}")
    print(f"  {red}Errors:   {severity_counts['error']}{nc}")
    print(f"  {yellow}Warnings: {severity_counts['warning']}{nc}")
    print(f"  Info:     {severity_counts['info']}")
    print()

    if category_counts:
        print(f"{bold}Issues by Category:{nc}")
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cat}: {count}")
        print()

    if top_files:
        print(f"{bold}Top Files by Issues:{nc}")
        for filepath, count in top_files:
            print(f"  {filepath}: {count}")
        print()

    if passed:
        print(f"{green}{bold}✅ PASSED{nc} - Quality gate met")
    else:
        print(f"{red}{bold}❌ FAILED{nc} - Quality gate not met")
        if severity_counts["error"] > error_threshold:
            print(f"  Errors ({severity_counts['error']}) exceed threshold ({error_threshold})")
        if warning_threshold >= 0 and severity_counts["warning"] > warning_threshold:
            print(f"  Warnings ({severity_counts['warning']}) exceed threshold ({warning_threshold})")
