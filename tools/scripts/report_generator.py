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


def generate_junit_xml(results: list[Any]) -> str:
    """Generate JUnit XML report.

    Args:
        results: List of ValidationResult objects (duck-typed)
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_tests = len(results)
    failures = sum(1 for r in results if not r.passed)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="language-rules" tests="{total_tests}" '
        f'failures="{failures}" errors="{total_errors}" warnings="{total_warnings}">',
    ]

    for result in results:
        testcase = f'  <testcase name="{_xml_escape(result.file)}" classname="{result.language}">'
        if not result.passed:
            for issue in result.issues:
                if issue.severity == "error":
                    lines.append(f"{testcase}")
                    lines.append(f'    <failure message="{_xml_escape(issue.message)}">')
                    lines.append(f"      {issue.rule_id}: {issue.message} (line {issue.line})")
                    lines.append("    </failure>")
                    lines.append("  </testcase>")
                    break
            else:
                lines.append(f"{testcase}</testcase>")
        else:
            # Report warnings as system-out
            warns = [i for i in result.issues if i.severity == "warning"]
            if warns:
                lines.append(f"{testcase}")
                lines.append("    <system-out>")
                for w in warns[:5]:
                    lines.append(f"      [{w.rule_id}] {w.message} (line {w.line})")
                lines.append("    </system-out>")
                lines.append("  </testcase>")
            else:
                lines.append(f"{testcase}</testcase>")

    lines.append("</testsuite>")
    return "\n".join(lines)


def generate_html_report(results: list[Any]) -> str:
    """Generate HTML report.

    Args:
        results: List of ValidationResult objects (duck-typed)
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)
    passed_count = sum(1 for r in results if r.passed)

    rows = []
    for result in sorted(results, key=lambda r: (not r.passed, r.file)):
        status_class = "pass" if result.passed else "fail"
        rows.append(f"""      <tr class="{status_class}">
        <td>{_html_escape(result.file)}</td>
        <td>{result.language}</td>
        <td class="num">{result.error_count}</td>
        <td class="num">{result.warning_count}</td>
        <td class="num">{result.info_count}</td>
        <td>{"PASS" if result.passed else "FAIL"}</td>
      </tr>""")
        if not result.passed:
            for issue in result.issues[:3]:
                rows.append(f"""      <tr class="detail">
        <td colspan="6">[{issue.severity}] {issue.rule_id}: {_html_escape(issue.message)} (line {issue.line})</td>
      </tr>""")

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
    <div class="card pass"><strong>{passed_count}</strong> files passed</div>
    <div class="card error"><strong>{total_errors}</strong> errors</div>
    <div class="card warn"><strong>{total_warnings}</strong> warnings</div>
    <div class="card info"><strong>{total_info}</strong> info</div>
  </div>
  <table>
    <tr><th>File</th><th>Language</th><th>Errors</th><th>Warnings</th><th>Info</th><th>Status</th></tr>
{chr(10).join(rows)}
  </table>
</body>
</html>"""


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


def _build_sarif_results(results: list[Any]) -> list[dict[str, Any]]:
    """Build SARIF result entries from validation results."""
    runs_results: list[dict[str, Any]] = []
    for result in results:
        for issue in result.issues:
            level = "error" if issue.severity == "error" else "warning" if issue.severity == "warning" else "note"
            runs_results.append(
                {
                    "ruleId": issue.rule_id,
                    "level": level,
                    "message": {"text": issue.message},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": result.file},
                                "region": {
                                    "startLine": issue.line,
                                    "startColumn": getattr(issue, "column", 1) or 1,
                                },
                            }
                        }
                    ],
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


def write_report(results: list[Any], format: str, output: Path | None = None) -> str | None:
    """Write report in specified format. Returns content or writes to file.

    Args:
        results: List of ValidationResult objects (duck-typed)
        format: Output format (json, junit, html, sarif)
        output: Optional file path to write to
    """
    if format == "json":
        data = {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total_files": len(results),
                "total_errors": sum(r.error_count for r in results),
                "total_warnings": sum(r.warning_count for r in results),
                "total_info": sum(r.info_count for r in results),
                "passed": all(r.passed for r in results),
            },
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
    elif format == "junit":
        content = generate_junit_xml(results)
    elif format == "html":
        content = generate_html_report(results)
    elif format == "sarif":
        content = generate_sarif(results)
    else:
        return None

    if output:
        output.write_text(content, encoding="utf-8")
        print(f"Report written to {output}", file=sys.stderr)
    return content
