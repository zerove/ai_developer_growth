from __future__ import annotations

import argparse
import json


def cmd_bench(args: argparse.Namespace) -> int:
    """Run performance benchmarks."""
    from tools.benchmarks import run_all_benchmarks

    file_counts = [int(x) for x in args.files.split(",")]
    languages = [x.strip() for x in args.languages.split(",")]

    results = run_all_benchmarks(file_counts, languages)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0
