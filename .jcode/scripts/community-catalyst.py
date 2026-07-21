#!/usr/bin/env python3
"""
jcode Skill Runner - 社区催化剂

用法:
    python .jcode/scripts/community-catalyst.py triage
    python .jcode/scripts/community-catalyst.py validate
    python .jcode/scripts/community-catalyst.py stats
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


def triage() -> None:
    """分流 Issues"""
    print("🔍 分流 Issues...")
    labels = [
        "案例", "工具推荐", "方法论", "问题", "文档",
        "question", "bug", "enhancement", "good first issue"
    ]
    print("可用标签:")
    for label in labels:
        print(f"  - {label}")
    print("提示: 通过 GitHub CLI 标记 issue:")
    print("  gh issue edit <number> --add-label <label>")


def validate() -> None:
    """验证社区提交的案例"""
    print("✅ 验证社区案例...")
    code, output = run_command([
        sys.executable, "tools/scripts/validate_case_study.py", "--all"
    ])
    print(output)
    if code == 0:
        print("✅ 所有案例验证通过")
    else:
        print("❌ 部分案例验证失败")


def stats() -> None:
    """查看社区统计"""
    print("📊 社区统计...")
    case_dir = Path("case-studies")
    if not case_dir.exists():
        print("❌ 未找到案例目录")
        sys.exit(1)

    cases = list(case_dir.glob("*.md"))
    print(f"案例总数: {len(cases)}")

    # 统计来源
    sources = {"internal": 0, "community": 0}
    for case in cases:
        content = case.read_text(encoding="utf-8")
        if "来源: 社区贡献" in content or "来源: community" in content.lower():
            sources["community"] += 1
        else:
            sources["internal"] += 1

    print(f"内部案例: {sources['internal']}")
    print(f"社区案例: {sources['community']}")


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: community-catalyst.py <action>")
        print("Actions: triage, validate, stats")
        sys.exit(1)

    action = sys.argv[1]
    actions = {
        "triage": triage,
        "validate": validate,
        "stats": stats,
    }

    if action in actions:
        actions[action]()
    else:
        print(f"未知 action: {action}")
        print("可用 actions: " + ", ".join(actions.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()
