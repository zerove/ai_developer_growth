"""Quality Dashboard: FastAPI + SQLite web interface for code quality reports.

Usage:
    python -m tools.scripts.rules_engine.dashboard [--port PORT] [--db DB_PATH] [--ci-data-dir CI_DIR]

Dashboard shows:
- Quality trend charts (errors/warnings over time)
- File-level detail view
- Rule violation breakdown by category
- Historical comparison
- CI quality summary (from .quality-trends/summary.json)

API:
    GET  /             Dashboard HTML
    GET  /api/trend    Trend data (JSON)
    GET  /api/latest   Latest report (JSON)
    GET  /api/ci-summary  CI quality summary (JSON)
    POST /api/record   Record a quality run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.logger import logger


def init_db(db_path: str = "adg_quality.db") -> sqlite3.Connection:
    """Initialize SQLite database for quality tracking."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_files INTEGER,
            total_errors INTEGER,
            total_warnings INTEGER,
            total_info INTEGER,
            passed_files INTEGER,
            failed_files INTEGER,
            report_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            file_path TEXT,
            language TEXT,
            errors INTEGER,
            warnings INTEGER,
            info INTEGER,
            passed BOOLEAN,
            issues_json TEXT,
            FOREIGN KEY (run_id) REFERENCES quality_runs(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rule_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            rule_id TEXT,
            severity TEXT,
            count INTEGER,
            FOREIGN KEY (run_id) REFERENCES quality_runs(id)
        )
    """)
    conn.commit()
    return conn


def record_run(conn: sqlite3.Connection, report: dict[str, Any]) -> int:
    """Record a quality run result."""
    summary = report.get("summary", {})
    cursor = conn.execute(
        """INSERT INTO quality_runs
           (timestamp, total_files, total_errors, total_warnings, total_info,
            passed_files, failed_files, report_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(),
            summary.get("total_files", 0),
            summary.get("errors", 0),
            summary.get("warnings", 0),
            summary.get("info", 0),
            summary.get("passed", 0),
            summary.get("failed", 0),
            json.dumps(report, ensure_ascii=False),
        ),
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_trend_data(conn: sqlite3.Connection, limit: int = 30) -> list[dict[str, Any]]:
    """Get quality trend data for charts."""
    rows = conn.execute(
        """SELECT timestamp, total_files, total_errors, total_warnings,
                  passed_files, failed_files
           FROM quality_runs ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [
        {
            "timestamp": r[0],
            "total_files": r[1],
            "errors": r[2],
            "warnings": r[3],
            "passed": r[4],
            "failed": r[5],
        }
        for r in reversed(rows)
    ]


def get_latest_report(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Get the most recent full report."""
    row = conn.execute("SELECT report_json FROM quality_runs ORDER BY id DESC LIMIT 1").fetchone()
    if row and row[0]:
        return json.loads(row[0])  # type: ignore[no-any-return]
    return None


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADG Quality Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0f172a; color: #e2e8f0; }
        .header { background: #1e293b; padding: 20px 40px; border-bottom: 1px solid #334155; }
        .header h1 { font-size: 24px; color: #f8fafc; }
        .header .subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
        .stat-card .label { color: #94a3b8; font-size: 13px; text-transform: uppercase; }
        .stat-card .value { font-size: 32px; font-weight: 700; margin-top: 4px; }
        .stat-card .value.green { color: #22c55e; }
        .stat-card .value.red { color: #ef4444; }
        .stat-card .value.yellow { color: #eab308; }
        .stat-card .value.blue { color: #3b82f6; }
        .chart-container { background: #1e293b; border-radius: 12px; padding: 24px;
                          border: 1px solid #334155; margin-bottom: 24px; }
        .chart-container h2 { font-size: 16px; margin-bottom: 16px; color: #f8fafc; }
        .chart-wrapper { height: 300px; position: relative; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-size: 12px; text-transform: uppercase; font-weight: 600; }
        td { font-size: 14px; }
        .badge { padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        .badge-error { background: #7f1d1d; color: #fca5a5; }
        .badge-warning { background: #713f12; color: #fde047; }
        .badge-pass { background: #14532d; color: #86efac; }
        .badge-fail { background: #7f1d1d; color: #fca5a5; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 ADG Quality Dashboard</h1>
        <div class="subtitle">Code quality monitoring and trends</div>
    </div>
    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <div class="label">Total Files</div>
                <div class="value blue" id="total-files">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Errors</div>
                <div class="value red" id="total-errors">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Warnings</div>
                <div class="value yellow" id="total-warnings">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Status</div>
                <div class="value green" id="status">-</div>
            </div>
        </div>

        <div class="chart-container">
            <h2>Quality Trend</h2>
            <div class="chart-wrapper">
                <canvas id="trendChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h2>Latest File Results</h2>
            <table>
                <thead>
                    <tr><th>File</th><th>Language</th><th>Errors</th><th>Warnings</th><th>Status</th></tr>
                </thead>
                <tbody id="file-results"></tbody>
            </table>
        </div>
    </div>

    <script>
        const trendData = {{trend_data | safe}};
        const latestReport = {{latest_report | safe}};

        if (latestReport) {
            document.getElementById('total-files').textContent = latestReport.summary?.total_files || 0;
            document.getElementById('total-errors').textContent = latestReport.summary?.errors || 0;
            document.getElementById('total-warnings').textContent = latestReport.summary?.warnings || 0;
            const errors = latestReport.summary?.errors || 0;
            document.getElementById('status').textContent = errors > 0 ? 'FAIL' : 'PASS';
            document.getElementById('status').className = 'value ' + (errors > 0 ? 'red' : 'green');

            const tbody = document.getElementById('file-results');
            (latestReport.results || []).forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${r.file}</td><td>${r.language || '-'}</td>
                    <td>${r.errors || 0}</td><td>${r.warnings || 0}</td>
                    <td><span class="badge ${r.passed ? 'badge-pass' : 'badge-fail'}">${r.passed ? 'PASS' : 'FAIL'}</span></td>`;
                tbody.appendChild(tr);
            });
        }

        if (trendData.length > 0) {
            new Chart(document.getElementById('trendChart'), {
                type: 'line',
                data: {
                    labels: trendData.map(d => d.timestamp?.split('T')[0] || ''),
                    datasets: [{
                        label: 'Errors',
                        data: trendData.map(d => d.errors),
                        borderColor: '#ef4444',
                        backgroundColor: '#ef444440',
                        fill: true,
                    }, {
                        label: 'Warnings',
                        data: trendData.map(d => d.warnings),
                        borderColor: '#eab308',
                        backgroundColor: '#eab30840',
                        fill: true,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true } },
                    plugins: { legend: { labels: { color: '#e2e8f0' } } }
                }
            });
        }
    </script>
</body>
</html>"""


def create_app(db_path: str = "adg_quality.db", ci_data_dir: str | None = None) -> Any:
    """Create FastAPI app for the quality dashboard.

    Args:
        db_path: SQLite database path.
        ci_data_dir: Optional path to CI-generated quality data (.quality-trends/).
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
    except ImportError:
        logger.info("Error: FastAPI required. Install: pip install fastapi uvicorn", file=sys.stderr)
        sys.exit(1)

    app = FastAPI(title="ADG Quality Dashboard")
    conn = init_db(db_path)

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        trend = get_trend_data(conn)
        latest = get_latest_report(conn)
        html = HTML_TEMPLATE.replace(
            "{{trend_data | safe}}",
            json.dumps(trend, ensure_ascii=False),
        ).replace(
            "{{latest_report | safe}}",
            json.dumps(latest, ensure_ascii=False) if latest else "null",
        )
        return html

    @app.get("/api/trend")
    def api_trend(limit: int = 30) -> list[dict[str, Any]]:
        return get_trend_data(conn, limit)

    @app.get("/api/latest")
    def api_latest() -> dict[str, Any] | None:
        return get_latest_report(conn)

    @app.get("/api/ci-summary")
    def api_ci_summary() -> dict[str, Any] | None:
        """Read CI-generated quality summary if available."""
        ci_dir = ci_data_dir
        if not ci_dir:
            ci_dir = str(Path.cwd() / ".quality-trends")
        summary_file = Path(ci_dir) / "summary.json"
        if summary_file.exists():
            try:
                return json.loads(summary_file.read_text())
            except Exception:
                pass
        return None

    @app.post("/api/record")
    def api_record(report: dict[str, Any]) -> dict[str, Any]:
        run_id = record_run(conn, report)
        return {"run_id": run_id, "status": "recorded"}

    return app


def main() -> None:
    """Run the quality dashboard server."""
    parser = argparse.ArgumentParser(description="ADG Quality Dashboard")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--db", default="adg_quality.db", help="SQLite database path")
    parser.add_argument("--ci-data-dir", default=None, help="CI quality data directory (.quality-trends/)")
    args = parser.parse_args()

    app = create_app(args.db, ci_data_dir=args.ci_data_dir)

    try:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=args.port)  # nosec - dev only
    except ImportError:
        logger.info("Error: uvicorn required. Install: pip install uvicorn", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
