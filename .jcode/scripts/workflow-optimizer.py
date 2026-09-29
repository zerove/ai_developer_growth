#!/usr/bin/env python3
"""
jcode Skill Runner - 工作流优化师

用法:
    python .jcode/scripts/workflow-optimizer.py analyze
    python .jcode/scripts/workflow-optimizer.py recommend
    python .jcode/scripts/workflow-optimizer.py report
"""

import sys

from _common import get_project_root, print_section


def analyze() -> int:
    """分析效率数据"""
    print_section("效率数据分析")
    case_dir = get_project_root() / "docs" / "case-studies"
    if not case_dir.exists():
        print("❌ 未找到案例目录")
        return 1

    cases = list(case_dir.glob("*.md"))
    print(f"案例总数: {len(cases)}")

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
    return 0


def recommend() -> int:
    """推荐工具组合"""
    print_section("工具组合推荐")
    tool_matrix = get_project_root() / "docs" / "tools" / "ai-tool-matrix.md"
    if not tool_matrix.exists():
        print("❌ 未找到工具矩阵文档")
        return 1

    content = tool_matrix.read_text(encoding="utf-8")
    print("当前工具矩阵:")
    for line in content.split("\n"):
        if line.startswith("|") and "模型" not in line and "---" not in line:
            print(f"  {line[:70]}...")
    return 0


def report() -> int:
    """生成效率报告"""
    print_section("效率报告")
    root = get_project_root()

    stats = {
        "cases": (
            len(list((root / "docs" / "case-studies").glob("*.md"))) if (root / "docs" / "case-studies").exists() else 0
        ),
        "docs": (len(list((root / "docs").rglob("*.md"))) if (root / "docs").exists() else 0),
        "examples": (
            len([d for d in (root / "examples").iterdir() if d.is_dir()]) if (root / "examples").exists() else 0
        ),
    }

    print("=" * 50)
    print("AI Developer Growth - 效率报告")
    print("=" * 50)
    print(f"案例数量: {stats['cases']}")
    print(f"文档数量: {stats['docs']}")
    print(f"代码示例: {stats['examples']}")
    print("=" * 50)
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: workflow-optimizer.py <action>")
        print("Actions: analyze, recommend, report")
        sys.exit(1)

    action = sys.argv[1]

    action_map = {
        "analyze": analyze,
        "recommend": recommend,
        "report": report,
    }

    if action in action_map:
        sys.exit(action_map[action]())
    else:
        print(f"❌ 未知 action: {action}")
        print(f"可用 actions: {', '.join(action_map.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
