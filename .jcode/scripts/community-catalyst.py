#!/usr/bin/env python3
"""
jcode Skill Runner - 社区催化剂

用法:
    python .jcode/scripts/community-catalyst.py triage
    python .jcode/scripts/community-catalyst.py validate
    python .jcode/scripts/community-catalyst.py stats
"""

import sys

from _common import get_project_root, print_check, print_section, run_command


def triage() -> int:
    """分流 Issues"""
    print_section("Issue 分流")
    labels = ["案例", "工具推荐", "方法论", "问题", "文档", "question", "bug", "enhancement", "good first issue"]
    print("可用标签:")
    for label in labels:
        print(f"  - {label}")
    print("\n提示: 通过 GitHub CLI 标记 issue:")
    print("  gh issue edit <number> --add-label <label>")
    return 0


def validate() -> int:
    """验证社区提交的案例"""
    print_section("社区案例验证")
    code, output = run_command([sys.executable, "tools/scripts/validate_case_study.py", "--all"])
    print_check("案例验证", code == 0, output)
    if code != 0:
        print(output)
    return code


def stats() -> int:
    """查看社区统计"""
    print_section("社区统计")
    case_dir = get_project_root() / "case-studies"
    if not case_dir.exists():
        print("❌ 未找到案例目录")
        return 1

    cases = list(case_dir.glob("*.md"))
    print(f"案例总数: {len(cases)}")

    sources = {"internal": 0, "community": 0}
    for case in cases:
        content = case.read_text(encoding="utf-8")
        if "来源: 社区贡献" in content or "来源: community" in content.lower():
            sources["community"] += 1
        else:
            sources["internal"] += 1

    print(f"内部案例: {sources['internal']}")
    print(f"社区案例: {sources['community']}")
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: community-catalyst.py <action>")
        print("Actions: triage, validate, stats")
        sys.exit(1)

    action = sys.argv[1]

    action_map = {
        "triage": triage,
        "validate": validate,
        "stats": stats,
    }

    if action in action_map:
        sys.exit(action_map[action]())
    else:
        print(f"❌ 未知 action: {action}")
        print(f"可用 actions: {', '.join(action_map.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
