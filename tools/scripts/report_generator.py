"""Report generators for language rules validation.

Provides JUnit XML, HTML, and SARIF report generation.
Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _xml_escape(s: str) -> str:
    """Escape XML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _html_escape(s: str) -> str:
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _count_summary_stats(results: list[Any]) -> tuple[int, int, int, int]:
    """汇总 4 项基础统计.

    V2.18 P3-3 拆分: 从 generate_junit_xml (C=14) 抽出.
    返回 (total_errors, total_warnings, total_tests, failures).

    Phase 33b-12 fix (ADR-052): failures 排除 skipped.
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_tests = len(results)
    failures = sum(1 for r in results if not r.passed and not getattr(r, "skipped", False))
    return total_errors, total_warnings, total_tests, failures


def _build_header_lines(
    total_errors: int,
    total_warnings: int,
    total_tests: int,
    failures: int,
) -> list[str]:
    """构建 JUnit XML 头部 (XML decl + testsuite 开标签).

    V2.18 P3-3 拆分: 从 generate_junit_xml (C=14) 抽出.
    """
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="language-rules" tests="{total_tests}" '
        f'failures="{failures}" errors="{total_errors}" warnings="{total_warnings}">',
    ]


def _build_failure_testcase(result: Any) -> list[str]:
    """构建失败 case 的 XML 块 (含 failure 子标签).

    V2.18 P3-3 拆分: 从 generate_junit_xml (C=14) 抽出.
    包含首个 error severity issue, 后续 issue 截断.
    """
    testcase = f'  <testcase name="{_xml_escape(result.file)}" classname="{result.language}">'
    lines = [testcase]
    for issue in result.issues:
        if issue.severity == "error":
            lines.append(f'    <failure message="{_xml_escape(issue.message)}">')
            lines.append(f"      {issue.rule_id}: {issue.message} (line {issue.line})")
            lines.append("    </failure>")
            lines.append("  </testcase>")
            return lines
    return [*lines, f"{testcase}</testcase>"]


def _build_pass_testcase(result: Any) -> list[str]:
    """构建通过 case 的 XML 块 (warning 作为 system-out).

    V2.18 P3-3 拆分: 从 generate_junit_xml (C=14) 抽出.
    无 warning 直接闭合, 有 warning 最多 5 条作为 system-out.

    Phase 33b-12 fix (ADR-052): skipped 文件用 <skipped/> 标记, 不算通过.
    """
    testcase = f'  <testcase name="{_xml_escape(result.file)}" classname="{result.language}">'
    # Phase 33b-12 fix: skipped 文件用 JUnit <skipped/> 标记
    if getattr(result, "skipped", False):
        return [f"{testcase}<skipped/></testcase>"]
    warns = [i for i in result.issues if i.severity == "warning"]
    if not warns:
        return [f"{testcase}</testcase>"]
    lines = [testcase, "    <system-out>"]
    for w in warns[:5]:
        lines.append(f"      [{w.rule_id}] {w.message} (line {w.line})")
    lines.extend(["    </system-out>", "  </testcase>"])
    return lines


def generate_junit_xml(results: list[Any]) -> str:
    """Generate JUnit XML report (orchestrator).

    V2.18 P3-3 拆分: 从 C=14 / 50 行主函数拆出 4 个 helper.
    主函数仅负责: 统计 → 头部 → 逐 case 构建 → 闭合.
    """
    total_errors, total_warnings, total_tests, failures = _count_summary_stats(results)
    lines = _build_header_lines(total_errors, total_warnings, total_tests, failures)

    for result in results:
        if result.passed:
            lines.extend(_build_pass_testcase(result))
        else:
            lines.extend(_build_failure_testcase(result))

    lines.append("</testsuite>")
    return "\n".join(lines)


def _count_severity_totals(results: list[Any]) -> dict[str, int]:
    """统计 results 中 errors / warnings / info 总数.

    V2.19 P3-33 拆分: 从 _count_html_summary (B=6) 抽出.
    """
    return {
        "total_errors": sum(r.error_count for r in results),
        "total_warnings": sum(r.warning_count for r in results),
        "total_info": sum(r.info_count for r in results),
    }


def _count_html_summary(results: list[Any]) -> dict[str, int]:
    """汇总 HTML 报告所需 4 项计数 (orchestrator).

    V2.19 P3-33 拆分: 从 B=6 / 10 行函数拆出 _count_severity_totals.
    主函数仅负责: 委托 severity 计数 + 追加 passed_count.

    Phase 33b-12 fix (ADR-052): passed_count 排除 skipped (skipped 不算通过).
    """
    summary = _count_severity_totals(results)
    summary["passed_count"] = sum(1 for r in results if r.passed and not getattr(r, "skipped", False))
    summary["skipped_count"] = sum(1 for r in results if getattr(r, "skipped", False))
    return summary


def _build_result_row(result: Any) -> list[str]:
    """构建单条 result 的 HTML 表格行 (含最多 3 条 detail).

    V2.18 P3-11 拆分: 从 generate_html_report (C=11) 抽出.
    """
    status_class = "pass" if result.passed else "fail"
    rows: list[str] = [
        f"""      <tr class="{status_class}">
        <td>{_html_escape(result.file)}</td>
        <td>{result.language}</td>
        <td class="num">{result.error_count}</td>
        <td class="num">{result.warning_count}</td>
        <td class="num">{result.info_count}</td>
        <td>{"PASS" if result.passed else "FAIL"}</td>
      </tr>"""
    ]
    if not result.passed:
        for issue in result.issues[:3]:
            rows.append(f"""      <tr class="detail">
        <td colspan="6">[{issue.severity}] {issue.rule_id}: {_html_escape(issue.message)} (line {issue.line})</td>
      </tr>""")
    return rows


def _build_html_template(counts: dict[str, int], table_rows: list[str]) -> str:
    """组装完整 HTML 文档 (含 CSS + summary + table).

    V2.18 P3-11 拆分: 从 generate_html_report (C=11) 抽出.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Language Rules Report</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
    .summary {{ display: flex; gap: 2rem; margin-bottom: 2rem; }}
    .card {{ padding: 1rem 1.5rem; border-radius: 8px; }}
    .card.error {{ background: #fee; border: 1px solid #fcc; }}
    .card.warn {{ background: #ffd; border: 1px solid #ff8; }}
    .card.pass {{ background: #efe; border: 1px solid #8c8; }}
    .card.info {{ background: #eef; border: 1px solid #88c; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ padding: 0.5rem 1rem; border: 1px solid #ddd; text-align: left; }}
    th {{ background: #f5f5f5; }}
    tr.pass td {{ background: #efe; }}
    tr.fail td {{ background: #fee; }}
    tr.detail td {{ background: #f9f9f9; font-size: 0.9em; color: #666; }}
    .num {{ text-align: right; }}
  </style>
</head>
<body>
  <h1>Language Rules Report</h1>
  <div class="summary">
    <div class="card pass"><strong>{counts["passed_count"]}</strong> files passed</div>
    <div class="card error"><strong>{counts["total_errors"]}</strong> errors</div>
    <div class="card warn"><strong>{counts["total_warnings"]}</strong> warnings</div>
    <div class="card info"><strong>{counts["total_info"]}</strong> info</div>
  </div>
  <table>
    <tr><th>File</th><th>Language</th><th>Errors</th><th>Warnings</th><th>Info</th><th>Status</th></tr>
{chr(10).join(table_rows)}
  </table>
</body>
</html>"""


def generate_html_report(results: list[Any]) -> str:
    """Generate HTML report (orchestrator).

    Args:
        results: List of ValidationResult objects (duck-typed)

    V2.18 P3-11 拆分: 从 C=11 / 63 行主函数拆出 3 个 helper.
    主函数仅负责: 排序 → 汇总 → 表格行 → HTML 模板.
    """
    counts = _count_html_summary(results)

    table_rows: list[str] = []
    for result in sorted(results, key=lambda r: (not r.passed, r.file)):
        table_rows.extend(_build_result_row(result))

    return _build_html_template(counts, table_rows)


def _build_sarif_rules(results: list[Any]) -> dict[str, dict[str, Any]]:
    """Build SARIF rule definitions from results."""
    rules: dict[str, dict[str, Any]] = {}
    for result in results:
        for issue in result.issues:
            if issue.rule_id not in rules:
                rules[issue.rule_id] = {
                    "id": issue.rule_id,
                    "shortDescription": {"text": issue.message},
                    "helpUri": f"https://github.com/example/rules/{issue.rule_id}",
                    "properties": {"category": issue.category},
                }
    return rules


def _map_severity_to_sarif_level(severity: str) -> str:
    """将 severity 映射到 SARIF level (error/warning/note).

    V2.19 P3-31 拆分: 从 _build_sarif_results (B=6) 抽出.
    """
    if severity == "error":
        return "error"
    if severity == "warning":
        return "warning"
    return "note"


def _build_sarif_result_entry(
    file_uri: str,
    rule_id: str,
    level: str,
    message: str,
    line: int,
    column: int,
) -> dict[str, Any]:
    """构造单条 SARIF result entry.

    V2.19 P3-31 拆分: 从 _build_sarif_results (B=6) 抽出.
    """
    return {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": file_uri},
                    "region": {
                        "startLine": line,
                        "startColumn": column or 1,
                    },
                }
            }
        ],
    }


def _build_sarif_results(results: list[Any]) -> list[dict[str, Any]]:
    """Build SARIF result entries from validation results (orchestrator).

    V2.19 P3-31 拆分: 从 B=6 / 27 行函数拆出 2 个 helper.
    Phase 33b-12 fix (ADR-052): skipped 文件现在用 result.kind='notApplicable'
    在 SARIF 中标记, 不再静默丢失.
    """
    runs_results: list[dict[str, Any]] = []
    for result in results:
        for issue in result.issues:
            level = _map_severity_to_sarif_level(issue.severity)
            runs_results.append(
                _build_sarif_result_entry(
                    file_uri=result.file,
                    rule_id=issue.rule_id,
                    level=level,
                    message=issue.message,
                    line=issue.line,
                    column=getattr(issue, "column", 1),
                )
            )
        # Phase 33b-12 fix: skipped 文件在 SARIF 中用 notApplicable 标记
        if getattr(result, "skipped", False) and not result.issues:
            runs_results.append(
                {
                    "ruleId": "file-skipped",
                    "level": "none",
                    "message": {"text": "File skipped (empty or unsupported)"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": result.file},
                            }
                        }
                    ],
                    "properties": {"kind": "notApplicable"},
                }
            )
    return runs_results


def generate_sarif(results: list[Any]) -> str:
    """Generate SARIF 2.1.0 report for GitHub Code Scanning.

    Args:
        results: List of ValidationResult objects (duck-typed)
    """
    rules = _build_sarif_rules(results)
    runs_results = _build_sarif_results(results)

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "language-rules",
                        "version": "1.0.0",
                        "rules": list(rules.values()),
                    }
                },
                "results": runs_results,
            }
        ],
    }

    return json.dumps(sarif, indent=2, ensure_ascii=False)


def _build_json_summary(results: list[Any]) -> dict[str, Any]:
    """构造 JSON 报告 summary 段 (total/计数 + passed).

    V2.19 P3-32 拆分: 从 _build_json_content (B=6) 抽出.

    Phase 33b-12 fix (ADR-052): passed 排除 skipped (仅在所有非 skipped 都 passed 时为 True).
    """
    non_skipped = [r for r in results if not getattr(r, "skipped", False)]
    return {
        "total_files": len(results),
        "total_errors": sum(r.error_count for r in results),
        "total_warnings": sum(r.warning_count for r in results),
        "total_info": sum(r.info_count for r in results),
        "passed": all(r.passed for r in non_skipped) if non_skipped else True,
    }


def _build_json_content(results: list[Any]) -> str:
    """构建 JSON 报告内容 (含 results + summary) (orchestrator).

    V2.19 P3-32 拆分: 从 B=6 / 16 行函数拆出 _build_json_summary.
    主函数仅负责: 拼装 data dict → 委托 summary → json.dumps.
    """
    data = {
        "results": [r.to_dict() for r in results],
        "summary": _build_json_summary(results),
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _generate_report_content(results: list[Any], format: str) -> str | None:
    """按 format 分发到对应生成器.

    V2.18 P3-10 拆分: 从 write_report (C=11) 抽出.
    返回 None = 未知 format.
    """
    if format == "json":
        return _build_json_content(results)
    if format == "junit":
        return generate_junit_xml(results)
    if format == "html":
        return generate_html_report(results)
    if format == "sarif":
        return generate_sarif(results)
    return None


def _write_or_return(content: str, output: Path | None) -> str:
    """写入文件或返回内容.

    V2.18 P3-10 拆分: 从 write_report (C=11) 抽出.
    有 output 时写入文件并 stderr 通知, 无时返回 content.
    """
    if output is None:
        return content
    output.write_text(content, encoding="utf-8")
    print(f"Report written to {output}", file=sys.stderr)
    return content


def write_report(results: list[Any], format: str, output: Path | None = None) -> str | None:
    """Write report in specified format (orchestrator).

    Returns content or writes to file.

    Args:
        results: List of ValidationResult objects (duck-typed)
        format: Output format (json, junit, html, sarif)
        output: Optional file path to write to

    V2.18 P3-10 拆分: 从 C=11 / 55 行主函数拆出 3 个 helper.
    主函数仅负责: 委托生成 → 委托写入.
    """
    content = _generate_report_content(results, format)
    if content is None:
        return None
    return _write_or_return(content, output)
