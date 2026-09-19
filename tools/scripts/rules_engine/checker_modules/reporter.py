"""结果报告生成模块。

支持多种输出格式：
- SARIF (Static Analysis Results Interchange Format)
- JUnit XML
- 纯文本报告
- JSON 结构化报告
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.scripts.rules_engine.models import CheckResult, Issue

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


def _append_sarif_result(sarif: dict[str, Any], result: CheckResult, issue: Issue) -> None:
    """向 SARIF runs 追加单条 issue 结果（供 generate_sarif_report 使用）。"""
    sarif["runs"][0]["results"].append(
        {
            "ruleId": issue.rule_id,
            "level": _severity_to_sarif_level(issue.severity),
            "message": {"text": issue.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": issue.file},
                        "region": {
                            "startLine": issue.line,
                            "startColumn": issue.column,
                            "endLine": issue.line,
                            "endColumn": issue.column + 1,
                        },
                    }
                }
            ],
        }
    )


def _update_sarif_rule_map(rule_map: dict[str, Any], issue: Issue) -> None:
    """更新 SARIF rule 映射（供 generate_sarif_report 使用）。"""
    rule_id = issue.rule_id
    if rule_id not in rule_map:
        rule_map[rule_id] = {
            "id": rule_id,
            "name": issue.category,
            "shortDescription": {"text": issue.message},
            "fullDescription": {"text": issue.message},
            "defaultConfiguration": {"level": _severity_to_sarif_level(issue.severity)},
        }


def generate_sarif_report(results: list[CheckResult], output_path: Path | None = None) -> str:
    """生成 SARIF 格式报告。

    Args:
        results: CheckResult 列表
        output_path: 可选输出路径，写入文件时返回路径

    Returns:
        SARIF JSON 字符串
    """
    import json

    sarif: dict[str, Any] = {
        "version": "2.1.0",
        "$schema": "https://schemastore.org/schemas/json/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "adg-rules-engine",
                        "informationUri": "https://github.com/zerove/ai_developer_growth",
                        "rules": [],
                    }
                },
                "results": [],
            }
        ],
    }

    rule_map: dict[str, Any] = {}

    for result in results:
        for issue in result.issues:
            _update_sarif_rule_map(rule_map, issue)
            _append_sarif_result(sarif, result, issue)

    sarif["runs"][0]["tool"]["driver"]["rules"] = list(rule_map.values())

    output = json.dumps(sarif, indent=2, ensure_ascii=False)

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        return str(output_path)
    return output


def _append_junit_testcase(testsuite: Element, result: CheckResult, issue: Issue) -> None:
    """向 JUnit testsuite 追加单条 testcase（供 generate_junit_report 使用）。"""
    from xml.etree.ElementTree import SubElement

    testcase = SubElement(
        testsuite,
        "testcase",
        name=f"{result.file}:{issue.line}:{issue.rule_id}",
        classname=issue.category,
    )
    if issue.severity == "error":
        failure = SubElement(testcase, "failure", message=issue.message)
        failure.text = f"{result.file}:{issue.line}:{issue.column} - {issue.message}"
    elif issue.severity == "warning":
        # JUnit 没有 warning，用 system-out
        stdout = SubElement(testcase, "system-out")
        stdout.text = f"WARNING: {result.file}:{issue.line}:{issue.column} - {issue.message}"
    else:
        stdout = SubElement(testcase, "system-out")
        stdout.text = f"INFO: {result.file}:{issue.line}:{issue.column} - {issue.message}"


def generate_junit_report(results: list[CheckResult], output_path: Path | None = None) -> str:
    """生成 JUnit XML 格式报告。

    Args:
        results: CheckResult 列表
        output_path: 可选输出路径

    Returns:
        JUnit XML 字符串
    """
    from xml.dom import minidom
    from xml.etree.ElementTree import Element, SubElement, tostring

    testsuites = Element("testsuites")
    testsuite = SubElement(
        testsuites,
        "testsuite",
        name="adg-rules-engine",
        tests=str(sum(len(r.issues) for r in results)),
        failures=str(sum(i.severity == "error" for r in results for i in r.issues)),
        errors="0",
        skipped=str(sum(1 for r in results if r.skipped)),
    )

    for result in results:
        if result.skipped:
            testcase = SubElement(testsuite, "testcase", name=result.file, classname=result.language)
            SubElement(testcase, "skipped", message="File skipped")
            continue

        for issue in result.issues:
            _append_junit_testcase(testsuite, result, issue)

    rough = tostring(testsuites, "utf-8")
    reparsed = minidom.parseString(rough)
    output = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        return str(output_path)
    return output


def _build_text_summary(results: list[CheckResult]) -> list[str]:
    """生成文本报告摘要头部（供 generate_text_report 使用）。"""
    lines = []
    total_files = len(results)
    total_issues = sum(len(r.issues) for r in results)
    errors = sum(1 for r in results for i in r.issues if i.severity == "error")
    warnings = sum(1 for r in results for i in r.issues if i.severity == "warning")
    info = sum(1 for r in results for i in r.issues if i.severity == "info")
    skipped = sum(1 for r in results if r.skipped)

    lines.append(f"总文件数: {total_files}")
    lines.append(f"总问题数: {total_issues} (错误: {errors}, 警告: {warnings}, 信息: {info})")
    lines.append(f"跳过文件: {skipped}")
    return lines


def _format_text_issue(result: CheckResult, issue: Issue) -> str:
    """格式化单条 issue 为文本行（供 generate_text_report 使用）。"""
    severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
    return (
        f"  {severity_icon} [{issue.severity.upper()}] {issue.rule_id} "
        f"({result.file}:{issue.line}:{issue.column}) - {issue.message}"
    )


def generate_text_report(results: list[CheckResult], output_path: Path | None = None) -> str:
    """生成纯文本格式报告。

    Args:
        results: CheckResult 列表
        output_path: 可选输出路径

    Returns:
        文本报告字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append("ADG Rules Engine - 检查报告")
    lines.append("=" * 60)
    lines.append("")

    lines.extend(_build_text_summary(results))
    lines.append("")

    for result in results:
        if result.skipped:
            lines.append(f"⏭️  {result.file} - 跳过 ({result.language})")
            continue

        if not result.issues:
            lines.append(f"✅ {result.file} - 通过")
            continue

        lines.append(f"📄 {result.file} ({result.language}) - {len(result.issues)} 个问题")
        for issue in result.issues:
            lines.append(_format_text_issue(result, issue))
        lines.append("")

    output = "\n".join(lines)

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        return str(output_path)
    return output


def generate_json_report(results: list[CheckResult], output_path: Path | None = None) -> str:
    """生成 JSON 结构化报告。

    Args:
        results: CheckResult 列表
        output_path: 可选输出路径

    Returns:
        JSON 字符串
    """
    import json

    data = {
        "summary": {
            "total_files": len(results),
            "total_issues": sum(len(r.issues) for r in results),
            "errors": sum(1 for r in results for i in r.issues if i.severity == "error"),
            "warnings": sum(1 for r in results for i in r.issues if i.severity == "warning"),
            "info": sum(1 for r in results for i in r.issues if i.severity == "info"),
            "skipped_files": sum(1 for r in results if r.skipped),
        },
        "results": [r.to_dict() for r in results],
    }

    output = json.dumps(data, indent=2, ensure_ascii=False)

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        return str(output_path)
    return output


def _severity_to_sarif_level(severity: str) -> str:
    """将严重度映射为 SARIF 级别。"""
    return {"error": "error", "warning": "warning", "info": "note"}.get(severity, "none")
