"""Cross-Platform JCode Task Runner

Acts as a platform-agnostic alternative to Makefile, supporting Windows, macOS, and Linux
for running tests, linting, quality gates, and AI-Native SDLC workflows.
"""

from __future__ import annotations

import argparse

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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
