"""Cross-Platform JCode Task Runner

Acts as a platform-agnostic alternative to Makefile, supporting Windows, macOS, and Linux
for running tests, linting, quality gates, and AI-Native SDLC workflows.
"""

from __future__ import annotations

import argparse
import sys

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


from tools.scripts._common import get_project_root, run_command  # noqa: E402


def run_task(task_name: str) -> int:
    root = get_project_root()
    print(f"🚀 Running JCode Cross-Platform Task: '{task_name}'")

    commands = {
        "check": [sys.executable, "-m", "pytest", "tests/", "-q"],
        "semantic-graph": [
            sys.executable,
            str(root / "tools" / "scripts" / "semantic_code_graph.py"),
        ],
        "architecture-guard": [
            sys.executable,
            str(root / "tools" / "scripts" / "architecture_drift_guard.py"),
        ],
        "metrics-telemetry": [
            sys.executable,
            str(root / "tools" / "scripts" / "metrics_telemetry.py"),
        ],
        "workflow-ai-native": [
            sys.executable,
            str(root / "tools" / "scripts" / "jcode_ai_native_workflow.py"),
            "Cross-Platform Workflow Execution",
        ],
        "setup-wizard": [
            sys.executable,
            str(root / "tools" / "scripts" / "jcode_setup_wizard.py"),
        ],
        "dashboard": [
            sys.executable,
            str(root / "tools" / "scripts" / "ai_native_dashboard.py"),
        ],
    }

    if task_name not in commands:
        print(f"❌ Unknown task: {task_name}. Available tasks:")
        for name in commands:
            print(f"  - {name}")
        return 1

    exit_code, output = run_command(commands[task_name])
    if exit_code == 0:
        print(f"✅ Task '{task_name}' completed successfully.")
        return 0
    else:
        print(f"❌ Task '{task_name}' failed:\n{output}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="JCode Cross-Platform Task Runner (Alternative to Makefile)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available tasks:\n  check, semantic-graph, architecture-guard,\n  metrics-telemetry, workflow-ai-native, setup-wizard,\n  dashboard",
    )
    parser.add_argument("task", help="Task name to run")
    args = parser.parse_args()
    sys.exit(run_task(args.task))
