"""AI-Native SDLC Interactive Terminal Dashboard (Phase 3)

Provides a clean terminal UI showing semantic graph nodes, architecture compliance,
AI slop scan findings, and telemetry metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts._common import get_project_root


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
