from __future__ import annotations

import argparse

from ._shared import (
    _TREND_DATA_FILE,
    Path,
    _format_trend_report,
    _load_trend_data,
)


def cmd_trend(args: argparse.Namespace) -> int:
    """Show quality trend dashboard."""
    project_dir = Path(args.path).resolve()

    if getattr(args, "clear", False):
        trend_file = project_dir / _TREND_DATA_FILE
        if trend_file.exists():
            trend_file.unlink()
            print("Trend history cleared.")
        else:
            print("No trend history to clear.")
        return 0

    trend_data = _load_trend_data(project_dir)

    if getattr(args, "json", False):
        print(_format_trend_report(trend_data, output_json=True))
    else:
        print(_format_trend_report(trend_data))

    return 0
