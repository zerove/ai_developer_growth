"""
ADG HTML Report Generator - Beautiful quality gate reports.

Usage:
    from tools.report.html_report import generate_html_report
    html = generate_html_report(issues, language, framework, files_checked)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli import Issue


def generate_html_report(
    issues: list[Issue],
    language: str,
    framework: str | None = None,
    files_checked: int = 0,
    title: str = "ADG Governance Report",
) -> str:
    """Generate a beautiful HTML quality gate report."""
    error_count = sum(1 for i in issues if i.severity == "error")
    warn_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    # Group by category
    categories: dict[str, int] = {}
    for issue in issues:
        cat = issue.category or "unknown"
        categories[cat] = categories.get(cat, 0) + 1

    # Group by file
    file_issues: dict[str, list[Issue]] = {}
    for issue in issues:
        file_issues.setdefault(issue.file, []).append(issue)

    # Top files
    top_files = sorted(file_issues.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    # Pass/fail
    passed = error_count == 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #0d1117; --surface: #161b22; --border: #30363d;
            --text: #e6edf3; --text-dim: #8b949e;
            --red: #f85149; --green: #3fb950; --yellow: #d29922; --blue: #58a6ff;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
               background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
        .meta {{ color: var(--text-dim); margin-bottom: 2rem; font-size: 0.9rem; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem; text-align: center; }}
        .card-value {{ font-size: 2rem; font-weight: bold; }}
        .card-label {{ color: var(--text-dim); font-size: 0.85rem; margin-top: 0.3rem; }}
        .card-error .card-value {{ color: var(--red); }}
        .card-warn .card-value {{ color: var(--yellow); }}
        .card-info .card-value {{ color: var(--blue); }}
        .card-pass .card-value {{ color: var(--green); }}
        .card-fail .card-value {{ color: var(--red); }}
        .section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }}
        .section h2 {{ font-size: 1.2rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ text-align: left; padding: 0.6rem 1rem; border-bottom: 1px solid var(--border); }}
        th {{ color: var(--text-dim); font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
        tr:hover {{ background: rgba(255,255,255,0.03); }}
        .severity-error {{ color: var(--red); font-weight: 600; }}
        .severity-warning {{ color: var(--yellow); font-weight: 600; }}
        .severity-info {{ color: var(--blue); font-weight: 600; }}
        .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
        .badge-error {{ background: rgba(248,81,73,0.15); color: var(--red); }}
        .badge-warn {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
        .badge-info {{ background: rgba(88,166,255,0.15); color: var(--blue); }}
        .bar-chart {{ margin-top: 1rem; }}
        .bar-row {{ display: flex; align-items: center; margin-bottom: 0.5rem; }}
        .bar-label {{ width: 120px; font-size: 0.85rem; color: var(--text-dim); }}
        .bar {{ height: 24px; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 0.8rem; font-weight: 600; color: white; min-width: 30px; }}
        .bar-error {{ background: var(--red); }}
        .bar-warn {{ background: var(--yellow); }}
        .bar-info {{ background: var(--blue); }}
        .footer {{ text-align: center; color: var(--text-dim); font-size: 0.8rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
    </style>
</head>
<body>
<div class="container">
    <h1>🛡️ {title}</h1>
    <div class="meta">
        Language: <strong>{language}</strong>
        {f' &middot; Framework: <strong>{framework}</strong>' if framework else ''}
        &middot; Files: <strong>{files_checked}</strong>
        &middot; Generated: <strong>{now}</strong>
    </div>

    <div class="cards">
        <div class="card {'card-pass' if passed else 'card-fail'}">
            <div class="card-value">{'✅ PASS' if passed else '❌ FAIL'}</div>
            <div class="card-label">Quality Gate</div>
        </div>
        <div class="card card-error">
            <div class="card-value">{error_count}</div>
            <div class="card-label">Errors</div>
        </div>
        <div class="card card-warn">
            <div class="card-value">{warn_count}</div>
            <div class="card-label">Warnings</div>
        </div>
        <div class="card card-info">
            <div class="card-value">{info_count}</div>
            <div class="card-label">Info</div>
        </div>
        <div class="card">
            <div class="card-value">{len(issues)}</div>
            <div class="card-label">Total Issues</div>
        </div>
    </div>
"""

    # Category breakdown chart
    if categories:
        max_count = max(categories.values()) if categories else 1
        html += '    <div class="section">\n        <h2>Issues by Category</h2>\n        <div class="bar-chart">\n'
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            width_pct = int(count / max_count * 100)
            bar_class = "bar-error" if cat == "security" else ("bar-warn" if cat == "performance" else "bar-info")
            html += f'            <div class="bar-row"><span class="bar-label">{cat}</span>'
            html += f'<div class="bar {bar_class}" style="width:{width_pct}%">{count}</div></div>\n'
        html += '        </div>\n    </div>\n'

    # Top files table
    if top_files:
        html += '    <div class="section">\n        <h2>Top Files by Issues</h2>\n'
        html += '        <table><thead><tr><th>File</th><th>Issues</th><th>Errors</th><th>Warnings</th></tr></thead><tbody>\n'
        for filepath, file_issue_list in top_files:
            fe = sum(1 for i in file_issue_list if i.severity == "error")
            fw = sum(1 for i in file_issue_list if i.severity == "warning")
            name = Path(filepath).name
            html += f'            <tr><td>{name}</td><td>{len(file_issue_list)}</td>'
            html += f'<td class="severity-error">{fe}</td>'
            html += f'<td class="severity-warning">{fw}</td></tr>\n'
        html += '        </tbody></table>\n    </div>\n'

    # Issues table
    if issues:
        html += '    <div class="section">\n'
        html += f'        <h2>All Issues ({len(issues)})</h2>\n'
        html += '        <table><thead><tr><th>Severity</th><th>Rule</th><th>File</th><th>Line</th><th>Message</th><th>Fix Hint</th></tr></thead><tbody>\n'
        for issue in sorted(issues, key=lambda i: {"error": 0, "warning": 1, "info": 2}.get(i.severity, 3)):
            badge_class = f"badge-{issue.severity[0]}" if issue.severity in ("error", "warning") else "badge-info"
            html += f'            <tr><td><span class="badge {badge_class}">{issue.severity.upper()}</span></td>'
            html += f'<td><code>{issue.rule_id}</code></td>'
            html += f'<td>{Path(issue.file).name}</td>'
            html += f'<td>{issue.line}</td>'
            html += f'<td>{issue.message}</td>'
            html += f'<td>{issue.fix_hint}</td></tr>\n'
        html += '        </tbody></table>\n    </div>\n'

    html += f"""
    <div class="footer">
        Generated by ADG Governance &middot; AI Developer Growth
    </div>
</div>
</body>
</html>"""

    return html


def save_html_report(
    issues: list[Issue],
    output_path: str | Path,
    language: str = "unknown",
    framework: str | None = None,
    files_checked: int = 0,
) -> Path:
    """Generate and save HTML report to file."""
    html = generate_html_report(issues, language, framework, files_checked)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
