from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.core import Issue

_TREND_DATA_FILE = ".adg/trend.json"


def _load_trend_data(project_dir: Path) -> list[dict[str, Any]]:
    """Load historical trend data."""
    trend_file = project_dir / _TREND_DATA_FILE
    if trend_file.exists():
        try:
            result: list[dict[str, Any]] = json.loads(trend_file.read_text(encoding="utf-8"))
            return result
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_trend_data(project_dir: Path, data: list[dict[str, Any]]) -> None:
    """Save trend data."""
    trend_file = project_dir / _TREND_DATA_FILE
    trend_file.parent.mkdir(parents=True, exist_ok=True)
    trend_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _record_trend(project_dir: Path, issues: list[Issue], language: str) -> dict[str, Any]:
    """Record current check results as a trend data point."""
    from datetime import datetime

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    data_point = {
        "timestamp": datetime.now().isoformat(),
        "language": language,
        "errors": error_count,
        "warnings": warning_count,
        "info": info_count,
        "total": len(issues),
        "files_checked": len(set(i.file for i in issues)),
    }

    trend_data = _load_trend_data(project_dir)
    trend_data.append(data_point)

    # Keep last 100 data points
    if len(trend_data) > 100:
        trend_data = trend_data[-100:]

    _save_trend_data(project_dir, trend_data)
    return data_point


def _format_trend_report(trend_data: list[dict[str, Any]], output_json: bool = False) -> str:
    """Format trend data as a report."""
    if not trend_data:
        return "No trend data available. Run 'adg check' first."

    if output_json:
        return json.dumps(trend_data, indent=2)

    lines = ["ADG Quality Trend Report", "=" * 40, ""]

    # Summary
    latest = trend_data[-1]
    earliest = trend_data[0]

    lines.append(f"Period: {earliest['timestamp'][:10]} to {latest['timestamp'][:10]}")
    lines.append(f"Data points: {len(trend_data)}")
    lines.append("")

    # Trend
    if len(trend_data) >= 2:
        error_trend = latest["errors"] - earliest["errors"]
        warning_trend = latest["warnings"] - earliest["warnings"]

        lines.append("Trend:")
        lines.append(
            f"  Errors:   {latest['errors']} ({'↑' if error_trend > 0 else '↓' if error_trend < 0 else '→'} {abs(error_trend)})"
        )
        lines.append(
            f"  Warnings: {latest['warnings']} ({'↑' if warning_trend > 0 else '↓' if warning_trend < 0 else '→'} {abs(warning_trend)})"
        )
        lines.append("")

    # Recent history
    lines.append("Recent History:")
    lines.append("-" * 40)
    for point in trend_data[-10:]:
        ts = point["timestamp"][:16].replace("T", " ")
        lines.append(f"  {ts}: E={point['errors']} W={point['warnings']} I={point['info']}")

    return "\n".join(lines)
