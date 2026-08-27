from __future__ import annotations

import argparse
import logging


def cmd_lsp(args: argparse.Namespace) -> int:
    """Start ADG Language Server."""

    from tools.lsp.server import run_stdio_server, run_tcp_server

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    if args.stdio:
        run_stdio_server()
    else:
        run_tcp_server(args.port)
    return 0
