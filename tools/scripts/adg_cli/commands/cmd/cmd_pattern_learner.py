from __future__ import annotations

import argparse

from ._shared import (
    Path,
)


def cmd_pattern_learner(args: argparse.Namespace) -> int:
    """Learn team coding norms from codebase."""
    from tools.scripts.rules_engine.pattern_learner import PatternLearner

    target = Path(args.path).resolve()

    learner = PatternLearner()
    learner.MIN_OCCURRENCES = getattr(args, "min_occurrences", 3)
    patterns = learner.learn_from_directory(target)

    if getattr(args, "json", False):
        import json

        print(json.dumps(patterns, indent=2, ensure_ascii=False))
    else:
        print(f"🔍 AI 分析完成，发现 {len(patterns)} 个模式和建议")
        for p in patterns:
            freq = p.get("frequency", p.get("confidence", 0))
            conf = p.get("confidence", 0)
            ptype = p.get("type", "pattern")
            action = p.get("suggested_action", "")
            if freq > 0 or conf > 0:
                print(f"\n  [{ptype}] {p.get('message', p.get('pattern', ''))}")
                print(f"    置信度: {conf:.0%} | 建议: {action}")

    return 0
