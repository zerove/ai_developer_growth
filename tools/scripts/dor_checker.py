"""Definition-of-Ready (DoR) 7-Point Rubric Checker

Evaluates task intents and issue descriptions against a rigorous 7-point rubric
before dispatching to agents, preventing ambiguous or under-specified work (Garbage In, Garbage Out).
"""

from __future__ import annotations

import json

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from tools.scripts._common import get_project_root  # noqa: E402


class DoRChecker:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.rubric = [
            (
                "acceptance_criteria_testable",
                "Acceptance criteria must be binary-testable",
            ),
            ("no_unresolved_markers", "No unresolved markers (TBD, ???, etc.)"),
            ("named_references_resolve", "References to named things must resolve"),
            ("scope_bounded", "Scope must be strictly bounded"),
            ("affected_surface_named", "Affected file/module surface explicitly named"),
            ("done_state_describable", "End done-state clearly describable"),
            (
                "no_invisible_dependencies",
                "No invisible or untracked upstream dependencies",
            ),
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
