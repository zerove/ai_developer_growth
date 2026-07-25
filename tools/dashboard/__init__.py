"""
ADG Web Dashboard - Visual quality gate report.

Usage:
    from tools.dashboard.server import start_dashboard
    start_dashboard(port=8080, project_dir=".")

    # Or via CLI:
    python -m tools.dashboard.server --port 8080
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli import (
    check_directory,
    load_rules_for_language,
    detect_language,
    _load_trend_data,
    _format_trend_report,
    SKIP_DIRS,
    SKIP_EXTENSIONS,
)


# ─────────────────────────────────────────────────────────────
# HTML Dashboard
# ─────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADG Dashboard</title>
    <style>
        :root {{
            --bg: #0d1117; --surface: #161b22; --border: #30363d;
            --text: #e6edf3; --dim: #8b949e;
            --red: #f85149; --green: #3fb950; --yellow: #d29922;
            --blue: #58a6ff; --purple: #bc8cff;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
        .header {{ padding: 2rem; border-bottom: 1px solid var(--border); }}
        .header h1 {{ font-size: 1.5rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; padding: 2rem; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; }}
        .card h3 {{ color: var(--dim); font-size: 0.85rem; text-transform: uppercase; margin-bottom: 1rem; }}
        .stat {{ font-size: 2.5rem; font-weight: bold; }}
        .chart {{ width: 100%; height: 200px; position: relative; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid var(--border); }}
        th {{ color: var(--dim); font-size: 0.8rem; }}
        .bar {{ height: 20px; border-radius: 4px; min-width: 2px; transition: width 0.3s; }}
        .bar-err {{ background: var(--red); }}
        .bar-warn {{ background: var(--yellow); }}
        .bar-ok {{ background: var(--green); }}
        .refresh {{ position: fixed; bottom: 2rem; right: 2rem; background: var(--blue); color: white;
                    border: none; border-radius: 50%; width: 48px; height: 48px; font-size: 1.2rem;
                    cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ ADG Governance Dashboard</h1>
        <p style="color:var(--dim)">Project: {project_name} &middot; Language: {language} &middot; Updated: {timestamp}</p>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Quality Gate</h3>
            <div class="stat" style="color: {gate_color}">{gate_status}</div>
        </div>
        <div class="card">
            <h3>Issues by Severity</h3>
            <div class="stat" style="color: var(--red)">{error_count} errors</div>
            <div class="stat" style="color: var(--yellow)">{warn_count} warnings</div>
            <div class="stat" style="color: var(--blue)">{info_count} info</div>
        </div>
        <div class="card">
            <h3>Files Checked</h3>
            <div class="stat">{files_checked}</div>
        </div>
        <div class="card">
            <h3>Categories</h3>
            {category_bars}
        </div>
    </div>

    <div class="card" style="margin: 2rem;">
        <h3>Top Files by Issues</h3>
        <table>
            <thead><tr><th>File</th><th>Issues</th><th>Bar</th></tr></thead>
            <tbody>
                {file_rows}
            </tbody>
        </table>
    </div>

    <div class="card" style="margin: 0 2rem 2rem;">
        <h3>Recent Trend</h3>
        <table>
            <thead><tr><th>Date</th><th>Total</th><th>Errors</th><th>Warnings</th></tr></thead>
            <tbody>
                {trend_rows}
            </tbody>
        </table>
    </div>

    <button class="refresh" onclick="location.reload()" title="Refresh">↻</button>

    <script>
        // Auto-refresh every 60 seconds
        setTimeout(() => location.reload(), 60000);

        // Fetch data from API
        async function refreshData() {{
            try {{
                const resp = await fetch('/api/data');
                const data = await resp.json();
                document.title = `ADG: ${{data.summary.error}}E ${{data.summary.warning}}W`;
            }} catch(e) {{}}
        }}
    </script>
</body>
</html>"""


def generate_dashboard_html(
    project_dir: str | Path,
    output_path: str | Path | None = None,
) -> str:
    """Generate a static HTML dashboard."""
    project_dir = Path(project_dir)

    # Detect language
    detected = detect_language(project_dir)
    language = detected.get("language", "unknown")

    # Check files
    rules = load_rules_for_language(language)
    issues = check_directory(project_dir, rules)

    # Counts
    error_count = sum(1 for i in issues if i.severity == "error")
    warn_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")
    files_checked = len(set(i.file for i in issues))

    # Categories
    categories: dict[str, int] = {}
    for issue in issues:
        cat = issue.category or "unknown"
        categories[cat] = categories.get(cat, 0) + 1

    # Category bars
    max_cat = max(categories.values()) if categories else 1
    cat_bars = []
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:6]:
        width = int(count / max_cat * 100)
        cat_bars.append(
            f'<div style="margin: 0.3rem 0"><span style="width:100px;display:inline-block;color:var(--dim)">{cat}</span>'
            f'<div class="bar bar-ok" style="width:{width}%;display:inline-block">{count}</div></div>'
        )

    # File rows
    file_counts: dict[str, int] = {}
    for issue in issues:
        file_counts[issue.file] = file_counts.get(issue.file, 0) + 1
    top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    max_file = top_files[0][1] if top_files else 1
    file_rows = []
    for fp, count in top_files:
        width = int(count / max_file * 100)
        bar_class = "bar-err" if count > 5 else "bar-warn"
        file_rows.append(
            f"<tr><td>{Path(fp).name}</td><td>{count}</td>"
            f'<td><div class="bar {bar_class}" style="width:{width}%"></div></td></tr>'
        )

    # Trend
    trend_data = _load_trend_data(project_dir)
    trend_rows = []
    for point in trend_data[-7:]:
        ts = point.get("timestamp", "")[:10]
        trend_rows.append(
            f"<tr><td>{ts}</td><td>{point.get('total', 0)}</td>"
            f'<td style="color:var(--red)">{point.get("errors", 0)}</td>'
            f'<td style="color:var(--yellow)">{point.get("warnings", 0)}</td></tr>'
        )

    # Gate status
    passed = error_count == 0
    gate_color = "var(--green)" if passed else "var(--red)"
    gate_status = "✅ PASSED" if passed else "❌ FAILED"

    html = DASHBOARD_HTML.format(
        project_name=project_dir.name,
        language=language,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        gate_color=gate_color,
        gate_status=gate_status,
        error_count=error_count,
        warn_count=warn_count,
        info_count=info_count,
        files_checked=files_checked,
        category_bars="\n".join(cat_bars),
        file_rows="\n".join(file_rows),
        trend_rows="\n".join(trend_rows),
    )

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")

    return html


# ─────────────────────────────────────────────────────────────
# HTTP API Server (lightweight, no dependencies)
# ─────────────────────────────────────────────────────────────


def start_dashboard(
    project_dir: str = ".",
    port: int = 8080,
    host: str = "127.0.0.1",
) -> None:
    """Start a simple HTTP dashboard server."""
    import http.server
    import functools

    project = Path(project_dir).resolve()

    class DashboardHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                html = generate_dashboard_html(project)
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode())
            elif self.path == "/api/data":
                detected = detect_language(project)
                rules = load_rules_for_language(detected.get("language", "python"))
                issues = check_directory(project, rules)
                data = {
                    "language": detected.get("language"),
                    "summary": {
                        "error": sum(1 for i in issues if i.severity == "error"),
                        "warning": sum(1 for i in issues if i.severity == "warning"),
                        "info": sum(1 for i in issues if i.severity == "info"),
                    },
                    "total_issues": len(issues),
                    "files_checked": len(set(i.file for i in issues)),
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress logs

    server = http.server.HTTPServer((host, port), DashboardHandler)
    print(f"ADG Dashboard: http://{host}:{port}")
    print(f"Project: {project}")
    server.serve_forever()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ADG Dashboard")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--project", default=".")
    parser.add_argument("--static", help="Generate static HTML file")
    args = parser.parse_args()

    if args.static:
        generate_dashboard_html(args.project, args.static)
        print(f"Static dashboard saved to: {args.static}")
    else:
        start_dashboard(args.project, args.port, args.host)


if __name__ == "__main__":
    main()
