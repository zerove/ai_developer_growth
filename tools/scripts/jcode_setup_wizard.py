"""Interactive JCode AI-Native Setup Wizard

Zero-friction onboarding tool that initializes project structure, configures
.jcode/ directories, sets up MCP server config, and builds initial semantic graph.
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


class JCodeSetupWizard:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()

    def run_setup(self) -> None:
        print("=" * 60)
        print(" 🧙 JCODE AI-NATIVE SETUP WIZARD ")
        print("=" * 60)

        # 1. Create directories
        jcode_dir = self.root_dir / ".jcode" / "rules"
        jcode_dir.mkdir(parents=True, exist_ok=True)
        print("✅ Created .jcode/rules/ directory.")

        # 2. Configure opencode MCP config template
        mcp_config = {
            "mcp": {
                "ai-native-sdlc": {
                    "command": "python",
                    "args": ["-m", "tools.scripts.ai_native_mcp_server"],
                    "cwd": str(self.root_dir),
                }
            }
        }
        mcp_path = self.root_dir / "opencode.json"
        if not mcp_path.exists():
            mcp_path.write_text(json.dumps(mcp_config, indent=2), encoding="utf-8")
            print("✅ Generated opencode.json MCP configuration.")

        # 3. Build initial semantic graph
        from tools.scripts.semantic_code_graph import SemanticCodeGraph

        graph = SemanticCodeGraph(self.root_dir)
        graph.build_graph()
        out = self.root_dir / ".semantic_graph.json"
        graph.save_to_json(out)
        print(f"✅ Built semantic code knowledge graph ({len(graph.nodes)} nodes).")

        print("=" * 60)
        print(" 🎉 JCode AI-Native Environment Setup Complete!")
        print("=" * 60)


if __name__ == "__main__":
    wizard = JCodeSetupWizard()
    wizard.run_setup()
