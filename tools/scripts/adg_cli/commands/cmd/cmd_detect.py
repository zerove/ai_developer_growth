from __future__ import annotations

import argparse
import json

from ._shared import (
    Path,
    detect_language,
)


def cmd_detect(args: argparse.Namespace) -> int:
    """Detect project language and framework."""
    target = Path(args.path).resolve()
    result = detect_language(target)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Language:  {result['language']}")
        print(f"Framework: {result.get('framework') or 'N/A'}")
        print(f"Confidence: {result['confidence']}")

    return 0
