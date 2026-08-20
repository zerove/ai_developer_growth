"""AI-Native SDLC MCP (Model Context Protocol) Server (Phase 3)

Exposes semantic code queries, architecture guard checks, and red-team debates
as standard Model Context Protocol tools for AI assistants (Claude, Cursor, etc.).
"""

from __future__ import annotations

import json
import sys

from tools.scripts._common import get_project_root


class AINativeMCPServer:
    def __init__(self) -> None:
        self.root_dir = get_project_root()

    def handle_tool_call(
        self, tool_name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        if tool_name == "query_semantic_graph":
            symbol = arguments.get("symbol", "")
            graph_path = self.root_dir / ".semantic_graph.json"
            if not graph_path.exists():
                return {"status": "error", "message": "Semantic graph not built yet."}
            data = json.loads(graph_path.read_text(encoding="utf-8"))
            matches = [v for k, v in data.items() if symbol in k]
            return {"status": "success", "matches": matches[:10]}
        elif tool_name == "run_architecture_guard":
            from architecture_drift_guard import ArchitectureDriftGuard

            guard = ArchitectureDriftGuard(self.root_dir)
            violations = guard.check_layering()
            return {"status": "success", "violations": violations}
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    server = AINativeMCPServer()
    print("🤖 AI-Native SDLC MCP Server initialized and ready.", file=sys.stderr)
    # Simple stdin/stdout JSON-RPC protocol stub
    for line in sys.stdin:
        try:
            req = json.loads(line)
            tool = req.get("tool")
            args = req.get("arguments", {})
            res = server.handle_tool_call(tool, args)
            print(json.dumps(res))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.stdout.flush()
