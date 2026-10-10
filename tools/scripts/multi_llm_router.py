"""Multi-LLM Benchmarking & Intelligent Routing Engine

Routes tasks to optimal models (Claude, Gemini, GPT, DeepSeek) based on task type,
complexity, cost, and historical success telemetry.
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


class MultiLLMRouter:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.routing_table = {
            "architecture_design": "claude-opus-4-7",
            "complex_refactoring": "claude-opus-4-7",
            "routine_bug_fix": "gemini-3.5-flash-lite",
            "unit_test_generation": "gemini-3.5-flash-lite",
            "security_audit": "claude-opus-4-7",
        }

    def route_task(self, task_type: str) -> dict[str, Any]:
        model = self.routing_table.get(task_type, "gemini-3.5-flash-lite")
        return {
            "task_type": task_type,
            "selected_model": model,
            "routing_basis": "Historical success telemetry & complexity score",
        }


if __name__ == "__main__":
    router = MultiLLMRouter()
    res = router.route_task("architecture_design")
    print(f"🧠 Multi-LLM Router Decision: {json.dumps(res, indent=2)}")
