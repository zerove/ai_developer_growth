"""AI-Native SDLC Interactive Terminal Dashboard (Phase 3)

Provides a clean terminal UI showing semantic graph nodes, architecture compliance,
AI slop scan findings, and telemetry metrics.
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

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from tools.scripts._common import get_project_root  # noqa: E402


class AIDashboard:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()

    def render(self) -> None:
        print("=" * 60)
        print(" 🚀 AI-NATIVE SDLC DEVELOPER DASHBOARD ")
        print("=" * 60)

        import concurrent.futures

        def get_telemetry() -> str:
            telemetry_path = self.root_dir / ".quality-trends" / "telemetry.json"
            if telemetry_path.exists():
                return "📊 Telemetry Metrics:\n" + "\n".join(
                    [f"   - {k}: {v}" for k, v in json.loads(telemetry_path.read_text(encoding="utf-8")).items()]
                )
            return "📊 Telemetry: No metrics generated yet (run `make metrics-telemetry`)."

        def get_graph() -> str:
            graph_path = self.root_dir / ".semantic_graph.json"
            if graph_path.exists():
                gdata = json.loads(graph_path.read_text(encoding="utf-8"))
                return f"🕸️ Semantic Knowledge Graph: {len(gdata)} tracked nodes."
            return "🕸️ Semantic Graph: Not built yet (run `make semantic-graph`)."

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_telemetry = executor.submit(get_telemetry)
            future_graph = executor.submit(get_graph)

            print(future_telemetry.result())
            print(future_graph.result())

        print("=" * 60)
        print("✅ Dashboard rendered successfully.")


if __name__ == "__main__":
    dash = AIDashboard()
    dash.render()
