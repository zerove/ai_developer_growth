#!/usr/bin/env python3
"""
jcode Skill Runner - 工作流优化师

用法:
    python .jcode/scripts/workflow-optimizer.py analyze
    python .jcode/scripts/workflow-optimizer.py recommend
    python .jcode/scripts/workflow-optimizer.py report
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str]:
    """运行命令并返回结果"""
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=Path(__file__).parent.parent.parent
    )
    return result.returncode, result.stdout + result.stderr


def analyze() -> None:
    """分析效率数据"""
    print("📊 分析效率数据...")
    case_dir = Path("case-studies")
    if not case_dir.exists():
        print("❌ 未找到案例目录")
        sys.exit(1)

    cases = list(case_dir.glob("*.md"))
    print(f"案例总数: {len(cases)}")

    # 提取效率数据
    efficiencies = []
    for case in cases:
        content = case.read_text(encoding="utf-8")
        if "效率提升" in content:
            for line in content.split("\n"):
                if "效率提升" in line and "x" in line.lower():
                    efficiencies.append({"file": case.name, "line": line.strip()})

    print(f"有效率数据的案例: {len(efficiencies)}")
    for e in efficiencies[:5]:
        print(f"  - {e['file']}: {e['line'][:60]}...")
    if len(efficiencies) > 5:
        print(f"  ... 还有 {len(efficiencies) - 5} 个")


def recommend() -> None:
    """推荐工具组合"""
    print("🔧 推荐工具组合...")
    tool_matrix = Path("docs/tools/ai-tool-matrix.md")
    if not tool_matrix.exists():
        print("❌ 未找到工具矩阵文档")
        sys.exit(1)

    content = tool_matrix.read_text(encoding="utf-8")
    print("当前工具矩阵:")
    for line in content.split("\n"):
        if line.startswith("|") and "模型" not in line and "---" not in line:
            print(f"  {line[:70]}...")


def report() -> None:
    """生成效率报告"""
    print("📈 生成效率报告...")

    # 统计数据
    case_dir = Path("case-studies")
    docs_dir = Path("docs")
    examples_dir = Path("examples")

    stats = {
        "cases": len(list(case_dir.glob("*.md"))) if case_dir.exists() else 0,
        "docs": len(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else 0,
        "examples": len([d for d in examples_dir.iterdir() if d.is_dir()]) if examples_dir.exists() else 0,
    }

    print("=" * 50)
    print("AI Developer Growth - 效率报告")
    print("=" * 50)
    print(f"案例数量: {stats['cases']}")
    print(f"文档数量: {stats['docs']}")
    print(f"代码示例: {stats['examples']}")
    print("=" * 50)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: workflow-optimizer.py <action>")
        print("Actions: analyze, recommend, report")
        sys.exit(1)

    action = sys.argv[1]
    actions = {
        "analyze": analyze,
        "recommend": recommend,
        "report": report,
    }

    if action in actions:
        actions[action]()
    else:
        print(f"未知 action: {action}")
        print("可用 actions: " + ", ".join(actions.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()
