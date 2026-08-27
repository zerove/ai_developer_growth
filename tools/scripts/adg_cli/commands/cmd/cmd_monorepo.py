from __future__ import annotations

import argparse
import json


def cmd_monorepo(args: argparse.Namespace) -> int:
    """Check all projects in a monorepo."""
    from tools.multiproject import MonorepoChecker

    checker = MonorepoChecker(args.path)
    results = checker.check_all()

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(checker.generate_report(results))

    return 0 if results["total_summary"]["passed"] else 1
