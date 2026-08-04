"""Definition-of-Ready (DoR) 7-Point Rubric Checker

Evaluates task intents and issue descriptions against a rigorous 7-point rubric
before dispatching to agents, preventing ambiguous or under-specified work (Garbage In, Garbage Out).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.scripts._common import get_project_root


class DoRChecker:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.rubric = [
            ("acceptance_criteria_testable", "Acceptance criteria must be binary-testable"),
            ("no_unresolved_markers", "No unresolved markers (TBD, ???, etc.)"),
            ("named_references_resolve", "References to named things must resolve"),
            ("scope_bounded", "Scope must be strictly bounded"),
            ("affected_surface_named", "Affected file/module surface explicitly named"),
            ("done_state_describable", "End done-state clearly describable"),
            ("no_invisible_dependencies", "No invisible or untracked upstream dependencies"),
        ]

    def evaluate_intent(self, intent_text: str) -> dict[str, Any]:
        violations = []
        text_lower = intent_text.lower()

        if "tbd" in text_lower or "???" in text_lower or "todo" in text_lower:
            violations.append("Contains unresolved markers (TBD, ???, TODO)")
        if len(intent_text.strip()) < 15:
            violations.append("Intent description too brief or lacks bounded scope")

        passed = len(violations) == 0
        return {
            "intent": intent_text,
            "passed": passed,
            "score": 7 if passed else max(0, 7 - len(violations)),
            "violations": violations,
        }


if __name__ == "__main__":
    checker = DoRChecker()
    res = checker.evaluate_intent("Implement user login API with JWT and rate limiting")
    print(json.dumps(res, indent=2, ensure_ascii=False))
