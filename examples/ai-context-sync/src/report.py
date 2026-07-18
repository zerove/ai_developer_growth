"""Generate HTML audit reports for visualization."""

import html
import os
from typing import List, Dict, Any
from datetime import datetime


def generate_html_report(
    violations: List[Dict[str, Any]],
    adr_summary: str = "",
    project_name: str = "AI-Context-Sync Audit Report",
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    critical = [v for v in violations if v.get("severity") == "Critical"]
    warnings = [v for v in violations if v.get("severity") == "Warning"]
    infos = [v for v in violations if v.get("severity") == "Info"]

    violation_rows = ""
    for v in violations:
        sev = v.get("severity", "Unknown")
        color = {"Critical": "#dc3545", "Warning": "#ffc107", "Info": "#17a2b8"}.get(sev, "#6c757d")
        rule = html.escape(v.get("rule_id", ""))
        message = html.escape(v.get("message", ""))
        file_path = html.escape(v.get("file", ""))
        line = v.get("line", "")
        violation_rows += f"""
        <tr>
            <td><span style="color:{color};font-weight:bold">{sev}</span></td>
            <td><code>{rule}</code></td>
            <td>{message}</td>
            <td><code>{file_path}:{line}</code></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(project_name)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        .header {{ background: #343a40; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .header .timestamp {{ opacity: 0.7; }}
        .stats {{ display: flex; gap: 16px; margin-bottom: 20px; }}
        .stat {{ flex: 1; padding: 16px; border-radius: 8px; text-align: center; color: white; }}
        .stat-critical {{ background: #dc3545; }}
        .stat-warning {{ background: #ffc107; color: #333; }}
        .stat-info {{ background: #17a2b8; }}
        .stat-total {{ background: #6c757d; }}
        .stat h2 {{ margin: 0; font-size: 2em; }}
        .stat p {{ margin: 4px 0 0 0; opacity: 0.9; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }}
        th {{ background: #343a40; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #dee2e6; }}
        tr:hover {{ background: #f1f3f5; }}
        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
        .adr-summary {{ background: white; padding: 16px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }}
        .empty {{ text-align: center; padding: 40px; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{html.escape(project_name)}</h1>
            <div class="timestamp">Generated: {timestamp}</div>
        </div>
        <div class="stats">
            <div class="stat stat-critical"><h2>{len(critical)}</h2><p>Critical</p></div>
            <div class="stat stat-warning"><h2>{len(warnings)}</h2><p>Warning</p></div>
            <div class="stat stat-info"><h2>{len(infos)}</h2><p>Info</p></div>
            <div class="stat stat-total"><h2>{len(violations)}</h2><p>Total</p></div>
        </div>
        <div class="adr-summary"><h3>Architecture Context</h3><pre style="white-space:pre-wrap">{html.escape(adr_summary) if adr_summary else "No ADR context loaded."}</pre></div>
        <h3>Violations</h3>
        {"<table><thead><tr><th>Severity</th><th>Rule</th><th>Message</th><th>Location</th></tr></thead><tbody>" + violation_rows + "</tbody></table>" if violations else '<div class="empty">No violations found. All checks passed.</div>'}
    </div>
</body>
</html>"""


def save_report(html_content: str, output_path: str = "docs/audit-report.html") -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path
