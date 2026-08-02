"""Cross-Platform JCode Task Runner

Acts as a platform-agnostic alternative to Makefile, supporting Windows, macOS, and Linux
for running tests, linting, quality gates, and AI-Native SDLC workflows.
"""

from __future__ import annotations

import argparse
import sys

from tools.scripts._common import get_project_root, run_command


def run_task(task_name: str) -> int:
    root = get_project_root()
    print(f"🚀 Running JCode Cross-Platform Task: '{task_name}'")

    commands = {
        "check": [sys.executable, "-m", "pytest", "tests/test_ai_native_sdlc.py"],
        "semantic-graph": [sys.executable, str(root / "tools" / "scripts" / "semantic_code_graph.py")],
        "architecture-guard": [sys.executable, str(root / "tools" / "scripts" / "architecture_drift_guard.py")],
        "slop-scan": [sys.executable, str(root / "tools" / "scripts" / "ai_slop_scanner.py")],
        "metrics-telemetry": [sys.executable, str(root / "tools" / "scripts" / "metrics_telemetry.py")],
        "workflow-ai-native": [
            sys.executable,
            str(root / "tools" / "scripts" / "jcode_ai_native_workflow.py"),
            "Cross-Platform Workflow Execution",
        ],
        "swarm-run": [sys.executable, str(root / "tools" / "scripts" / "autonomous_swarm_engine.py")],
        "setup-wizard": [sys.executable, str(root / "tools" / "scripts" / "jcode_setup_wizard.py")],
        "dashboard": [sys.executable, str(root / "tools" / "scripts" / "ai_native_dashboard.py")],
        "self-evolve": [sys.executable, str(root / "tools" / "scripts" / "self_evolving_engine.py")],
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
        epilog="Available tasks:\n  check, semantic-graph, architecture-guard, slop-scan,\n  metrics-telemetry, workflow-ai-native, swarm-run, setup-wizard,\n  dashboard, self-evolve",
    )
    parser.add_argument("task", help="Task name to run")
    args = parser.parse_args()
    sys.exit(run_task(args.task))
