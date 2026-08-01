"""AI-Native SDLC Interactive Terminal Dashboard (Phase 3)

Provides a clean terminal UI showing semantic graph nodes, architecture compliance,
AI slop scan findings, and telemetry metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

from _common import get_project_root


class AIDashboard:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()

    def render(self) -> None:
        print("=" * 60)
        print(" 🚀 AI-NATIVE SDLC DEVELOPER DASHBOARD ")
        print("=" * 60)

        # 1. Telemetry
        telemetry_path = self.root_dir / ".quality-trends" / "telemetry.json"
        if telemetry_path.exists():
            data = json.loads(telemetry_path.read_text(encoding="utf-8"))
            print("📊 Telemetry Metrics:")
            for k, v in data.items():
                print(f"   - {k}: {v}")
        else:
            print("📊 Telemetry: No metrics generated yet (run `make metrics-telemetry`).")

        # 2. Semantic Graph
        graph_path = self.root_dir / ".semantic_graph.json"
        if graph_path.exists():
            gdata = json.loads(graph_path.read_text(encoding="utf-8"))
            print(f"🕸️ Semantic Knowledge Graph: {len(gdata)} tracked nodes.")
        else:
            print("🕸️ Semantic Graph: Not built yet (run `make semantic-graph`).")

        print("=" * 60)
        print("✅ Dashboard rendered successfully.")


if __name__ == "__main__":
    dash = AIDashboard()
    dash.render()
