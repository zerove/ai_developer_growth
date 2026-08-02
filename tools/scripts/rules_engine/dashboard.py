"""Quality Dashboard: FastAPI + SQLite web interface for code quality reports.

Usage:
    python -m tools.scripts.rules_engine.dashboard [--port PORT] [--db DB_PATH] [--ci-data-dir CI_DIR]

Dashboard shows:
- Quality trend charts (errors/warnings over time)
- File-level detail view
- Rule violation breakdown by category
- Historical comparison
- CI quality summary (from .quality-trends/summary.json)

API v2:
    GET  /             Dashboard HTML
    GET  /api/trend    Trend data (JSON)
    GET  /api/latest   Latest report (JSON)
    GET  /api/ci-summary  CI quality summary (JSON)
    POST /api/record   Record a quality run

API v3 (新增):
    GET  /api/v3/health         Service health check
    POST /api/v3/check          Run adg check remotely (--with-docs supported)
    GET  /api/v3/rules          List all available rules
    GET  /api/v3/rules/{rule_id}/docs  Get related docs for a rule
    GET  /api/v3/status         Dashboard aggregate status
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

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
        return cast(dict[str, Any], json.loads(row[0]))
    return None


def get_language_stats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Get language breakdown from the latest run."""
    latest_id = conn.execute("SELECT MAX(id) FROM quality_runs").fetchone()[0]
    if not latest_id:
        return []
    rows = conn.execute(
        """SELECT language, SUM(errors), SUM(warnings), SUM(info)
           FROM file_results WHERE run_id = ? GROUP BY language""",
        (latest_id,),
    ).fetchall()
    return [{"language": r[0], "errors": r[1] or 0, "warnings": r[2] or 0, "info": r[3] or 0} for r in rows]


def get_comparison(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Compare latest run with the run from ~7 days ago (week-over-week)."""
    latest = conn.execute(
        "SELECT id, total_errors, total_warnings, timestamp FROM quality_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not latest:
        return None
    # Find the closest run from ~7 days before the latest run
    prev = conn.execute(
        """SELECT id, total_errors, total_warnings, timestamp
           FROM quality_runs
           WHERE timestamp <= datetime(?, '-7 days')
           ORDER BY id DESC LIMIT 1""",
        (latest[3],),
    ).fetchone()
    if not prev:
        # Fallback: compare with the immediately preceding run
        prev = conn.execute(
            "SELECT id, total_errors, total_warnings, timestamp FROM quality_runs ORDER BY id DESC LIMIT 1 OFFSET 1"
        ).fetchone()
    if not prev:
        return None

    def pct(a: int, b: int) -> float:
        if b == 0:
            return 100.0 if a > 0 else 0.0
        return round((a - b) / b * 100, 1)

    return {
        "current_errors": latest[1],
        "previous_errors": prev[1],
        "errors_change": pct(latest[1], prev[1]),
        "current_warnings": latest[2],
        "previous_warnings": prev[2],
        "warnings_change": pct(latest[2], prev[2]),
        "current_timestamp": latest[3],
        "previous_timestamp": prev[3],
    }


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
        .chart-half { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-size: 12px; text-transform: uppercase; font-weight: 600; }
        td { font-size: 14px; }
        .badge { padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        .badge-error { background: #7f1d1d; color: #fca5a5; }
        .badge-warning { background: #713f12; color: #fde047; }
        .badge-pass { background: #14532d; color: #86efac; }
        .badge-fail { background: #7f1d1d; color: #fca5a5; }
        .arrow-up { color: #ef4444; }
        .arrow-down { color: #22c55e; }
        .comparison-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
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

        <div class="comparison-grid" id="comparison-cards"></div>

        <div class="chart-half">
            <div class="chart-container">
                <h2>Quality Trend (14 days)</h2>
                <div class="chart-wrapper">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
            <div class="chart-container">
                <h2>Language Distribution</h2>
                <div class="chart-wrapper">
                    <canvas id="langChart"></canvas>
                </div>
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
        const languageData = {{language_data | safe}};
        const comparisonData = {{comparison_data | safe}};

        // ── Stats Cards ──
        if (latestReport) {
            document.getElementById('total-files').textContent = latestReport.summary?.total_files || 0;
            document.getElementById('total-errors').textContent = latestReport.summary?.errors || 0;
            document.getElementById('total-warnings').textContent = latestReport.summary?.warnings || 0;
            const errors = latestReport.summary?.errors || 0;
            document.getElementById('status').textContent = errors > 0 ? 'FAIL' : 'PASS';
            document.getElementById('status').className = 'value ' + (errors > 0 ? 'red' : 'green');
        }

        // ── Comparison Cards ──
        if (comparisonData) {
            const grid = document.getElementById('comparison-cards');
            const cards = [
                { label: 'Errors vs Last Run', val: comparisonData.current_errors,
                  change: comparisonData.errors_change, prev: comparisonData.previous_errors },
                { label: 'Warnings vs Last Run', val: comparisonData.current_warnings,
                  change: comparisonData.warnings_change, prev: comparisonData.previous_warnings },
                { label: 'Change Trend', val: '',
                  change: (comparisonData.errors_change + comparisonData.warnings_change) / 2,
                  prev: '' },
            ];
            cards.forEach(c => {
                const dir = c.change < 0 ? '↓' : (c.change > 0 ? '↑' : '→');
                const cls = c.change < 0 ? 'arrow-down' : (c.change > 0 ? 'arrow-up' : '');
                const div = document.createElement('div');
                div.className = 'stat-card';
                div.innerHTML = `<div class="label">${c.label}</div>
                    <div class="value" style="font-size:24px">${c.val} <span class="${cls}">${dir}${Math.abs(c.change)}%</span></div>`;
                grid.appendChild(div);
            });
        }

        // ── Trend Chart (14 days default) ──
        const trendData14 = trendData.slice(-14);
        if (trendData14.length > 0) {
            new Chart(document.getElementById('trendChart'), {
                type: 'line',
                data: {
                    labels: trendData14.map(d => d.timestamp?.split('T')[0] || ''),
                    datasets: [{
                        label: 'Errors',
                        data: trendData14.map(d => d.errors),
                        borderColor: '#ef4444',
                        backgroundColor: '#ef444440',
                        fill: true,
                    }, {
                        label: 'Warnings',
                        data: trendData14.map(d => d.warnings),
                        borderColor: '#eab308',
                        backgroundColor: '#eab30840',
                        fill: true,
                    }, {
                        label: 'Passed',
                        data: trendData14.map(d => d.passed),
                        borderColor: '#22c55e',
                        backgroundColor: '#22c55e20',
                        fill: true,
                        borderDash: [5, 5],
                    }, {
                        label: 'Failed',
                        data: trendData14.map(d => d.failed),
                        borderColor: '#f43f5e',
                        backgroundColor: '#f43f5e20',
                        fill: true,
                        borderDash: [3, 3],
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

        // ── Language Distribution ──
        if (languageData && languageData.length > 0) {
            const colors = ['#3b82f6', '#ef4444', '#eab308', '#22c55e', '#a855f7', '#f97316', '#06b6d4', '#ec4899'];
            new Chart(document.getElementById('langChart'), {
                type: 'doughnut',
                data: {
                    labels: languageData.map(d => d.language),
                    datasets: [{
                        data: languageData.map(d => d.errors + d.warnings + d.info),
                        backgroundColor: languageData.map((_, i) => colors[i % colors.length]),
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { color: '#e2e8f0' } }
                    }
                }
            });
        }

        // ── File Results Table ──
        if (latestReport) {
            const tbody = document.getElementById('file-results');
            (latestReport.results || []).forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${r.file}</td><td>${r.language || '-'}</td>
                    <td>${r.errors || 0}</td><td>${r.warnings || 0}</td>
                    <td><span class="badge ${r.passed ? 'badge-pass' : 'badge-fail'}">${r.passed ? 'PASS' : 'FAIL'}</span></td>`;
                tbody.appendChild(tr);
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
        trend = get_trend_data(conn, 14)
        latest = get_latest_report(conn)
        lang_stats = get_language_stats(conn)
        comp = get_comparison(conn)
        html = (
            HTML_TEMPLATE.replace(
                "{{trend_data | safe}}",
                json.dumps(trend, ensure_ascii=False),
            )
            .replace(
                "{{latest_report | safe}}",
                json.dumps(latest, ensure_ascii=False) if latest else "null",
            )
            .replace(
                "{{language_data | safe}}",
                json.dumps(lang_stats, ensure_ascii=False),
            )
            .replace(
                "{{comparison_data | safe}}",
                json.dumps(comp, ensure_ascii=False) if comp else "null",
            )
        )
        return html

    @app.get("/api/trend")
    def api_trend(limit: int = 30) -> list[dict[str, Any]]:
        return get_trend_data(conn, limit)

    @app.get("/api/latest")
    def api_latest() -> dict[str, Any] | None:
        return get_latest_report(conn)

    @app.get("/api/languages")
    def api_languages() -> list[dict[str, Any]]:
        return get_language_stats(conn)

    @app.get("/api/comparison")
    def api_comparison() -> dict[str, Any] | None:
        return get_comparison(conn)

    @app.get("/api/ci-summary")
    def api_ci_summary() -> dict[str, Any] | None:
        """Read CI-generated quality summary if available."""
        ci_dir = ci_data_dir
        if not ci_dir:
            ci_dir = str(Path.cwd() / ".quality-trends")
        summary_file = Path(ci_dir) / "summary.json"
        if summary_file.exists():
            try:
                return cast(dict[str, Any], json.loads(summary_file.read_text()))
            except Exception:
                _ = None  # parse summary failed
        return None

    @app.post("/api/record")
    def api_record(report: dict[str, Any]) -> dict[str, Any]:
        run_id = record_run(conn, report)
        return {"run_id": run_id, "status": "recorded"}

    # ── Governance API v3 ─────────────────────────────────────

    @app.get("/api/v3/health")
    def api_v3_health() -> dict[str, Any]:
        """Health check endpoint."""
        db_ok = False
        try:
            conn.execute("SELECT 1")
            db_ok = True
        except Exception:
            pass
        return {
            "status": "ok",
            "version": "3.0.0",
            "uptime": datetime.now().isoformat(),
            "database": "connected" if db_ok else "error",
        }

    @app.post("/api/v3/check")
    def api_v3_check(
        path: str = ".",
        lang: str | None = None,
        with_docs: bool = False,
        severity: str | None = None,
    ) -> dict[str, Any]:
        """Run adg check remotely.

        Args:
            path: File or directory to check.
            lang: Force language (skip auto-detection).
            with_docs: Include related documentation links.
            severity: Filter by severity (error/warning/info).
        """
        cmd = ["adg", "check", path, "--json"]
        if lang:
            cmd.extend(["--lang", lang])
        if with_docs:
            cmd.append("--with-docs")
        if severity:
            cmd.extend(["--severity", severity])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return {"status": "error", "message": result.stderr or "Check failed"}
            data = json.loads(result.stdout)
            return {"status": "ok", "data": data}
        except FileNotFoundError:
            return {"status": "error", "message": "adg command not found"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Check timed out"}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Invalid JSON output: {e}"}

    @app.get("/api/v3/rules")
    def api_v3_rules(lang: str | None = None) -> dict[str, Any]:
        """List all available rules, optionally filtered by language."""
        try:
            from tools.scripts.adg_cli.rules import load_rules_for_language
        except ImportError:
            return {"status": "error", "message": "ADG rules module not available"}

        if lang:
            rules = load_rules_for_language(lang)
            return {"status": "ok", "language": lang, "rules": rules}
        # Return summary per language
        languages = [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "ruby",
            "kotlin",
            "swift",
            "csharp",
            "php",
        ]
        summary: dict[str, int] = {}
        for lang_id in languages:
            try:
                r = load_rules_for_language(lang_id)
                summary[lang_id] = len(r.get("anti_patterns", [])) + len(r.get("security_patterns", []))
            except Exception:
                summary[lang_id] = -1
        return {"status": "ok", "languages": summary}

    @app.get("/api/v3/rules/{rule_id}/docs")
    def api_v3_rule_docs(rule_id: str) -> dict[str, Any]:
        """Get related documentation for a specific rule."""
        mapping_path = Path(__file__).resolve().parent.parent.parent.parent / ".jcode" / "rule-docs-mapping.json"
        if not mapping_path.exists():
            return {"status": "ok", "rule_id": rule_id, "docs": [], "note": "No mapping cache found"}
        try:
            mapping = json.loads(mapping_path.read_text())
            docs = mapping.get(rule_id, [])
            return {"status": "ok", "rule_id": rule_id, "docs": docs, "count": len(docs)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to read mapping: {e}"}

    @app.get("/api/v3/status")
    def api_v3_status() -> dict[str, Any]:
        """Dashboard aggregate status across all dimensions."""
        trend = get_trend_data(conn, 14)
        latest = get_latest_report(conn)
        comp = get_comparison(conn)
        return {
            "status": "ok",
            "summary": {
                "trend_points": len(trend),
                "latest_report": latest.get("summary") if latest else None,
                "comparison": comp,
                "database_size": _get_db_size(db_path),
            },
        }

    return app


def _get_db_size(db_path: str) -> dict[str, Any]:
    """Get database file size info."""
    try:
        p = Path(db_path)
        if p.exists():
            return {"path": str(p.resolve()), "bytes": p.stat().st_size, "exists": True}
    except Exception:
        pass
    return {"path": db_path, "bytes": 0, "exists": False}


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
