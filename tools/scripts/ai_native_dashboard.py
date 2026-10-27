"""AI-Native SDLC Interactive Terminal Dashboard (Phase 3)

Provides a clean terminal UI showing semantic graph nodes, architecture compliance,
AI slop scan findings, and telemetry metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


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
