from __future__ import annotations

import argparse


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Start web dashboard or generate static HTML."""
    from tools.dashboard import generate_dashboard_html, start_dashboard

    if args.static:
        generate_dashboard_html(args.path, args.static)
        print(f"Static dashboard saved to: {args.static}")
        return 0

    start_dashboard(args.path, args.port, args.host)
    return 0
