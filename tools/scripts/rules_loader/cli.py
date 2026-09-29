"""Unified CLI helpers for all rule tools.

Provides common argparse arguments, output formatting, and error handling
to ensure consistency across all CLI scripts.

Usage:
    from rules.cli import add_common_args, output_results, cli_main
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.scripts._common import handle_error


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add standard CLI arguments to an argparse parser.

    Adds: --json, --format, --verbose, --output/-o
    """
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "html", "csv"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write output to file instead of stdout",
    )


def output_results(
    results: list[Any] | dict[str, Any] | str | Any,
    *,
    fmt: str = "text",
    json_output: bool = False,
    output_file: Path | None = None,
    verbose: bool = False,
    formatter: Callable[..., str] | None = None,
) -> int:
    """Output results in the specified format.

    Args:
        results: Data to output (list, dict, or str)
        fmt: Output format (text, json, html, csv)
        json_output: Legacy --json flag (overrides fmt to json)
        output_file: Optional file path to write to
        verbose: Whether to include verbose details
        formatter: Optional callable(data, verbose) -> str for text formatting

    Returns:
        0 on success
    """
    if json_output:
        fmt = "json"

    if fmt == "json":
        data: object
        if isinstance(results, list):
            data = [r.to_dict() if hasattr(r, "to_dict") else r for r in results]
        elif hasattr(results, "to_dict"):
            data = results.to_dict()
        else:
            data = results
        content = json.dumps(data, indent=2, ensure_ascii=False)
    elif formatter:
        content = formatter(results, verbose)
    elif isinstance(results, str):
        content = results
    else:
        content = str(results)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content)
        print(f"Output written to {output_file}")
    else:
        print(content)

    return 0


def cli_main(main_fn: Callable[[], int], script_name: str = "") -> None:
    """Wrapper for CLI main() with unified error handling (#9).

    Catches exceptions and delegates to handle_error from _common.
    """
    try:
        sys.exit(main_fn())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        handle_error(e, script=script_name or Path(sys.argv[0]).stem)
