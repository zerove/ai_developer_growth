#!/usr/bin/env python3
"""
jcode Skill Runner - 社区催化剂

用法:
    python .jcode/scripts/community-catalyst.py triage
    python .jcode/scripts/community-catalyst.py validate
    python .jcode/scripts/community-catalyst.py stats
    python .jcode/scripts/community-catalyst.py generate-adr [--pr PR_NUMBER]
    python .jcode/scripts/community-catalyst.py leaderboard
"""

import shutil
import subprocess
import sys

from _common import get_project_root, print_check, print_section, run_command


def triage() -> int:
    """分流 Issues"""
    print_section("Issue 分流")
    labels = [
        "案例",
        "工具推荐",
        "方法论",
        "问题",
        "文档",
        "question",
        "bug",
        "enhancement",
        "good first issue",
    ]
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


def _pr_ref() -> str:
    """解析 PR 引用。

    文档化的写法是 `generate-adr --pr 123`（见本文件 docstring、USAGE.md、
    registry.json），但早前直接取 sys.argv[2]，那个位置是 `--pr` 本身，
    于是命令变成 `adr_generator.py --pr --pr`，PR 号被丢弃。
    这里同时兼容 `--pr 123` 与裸位置参数 `generate-adr 123`。
    """
    args = sys.argv[2:]
    if "--pr" in args:
        idx = args.index("--pr")
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            return args[idx + 1]
        return "HEAD"
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return "HEAD"


def _resolve_title(ref: str) -> str:
    """从 PR / commit 引用解析决策标题。

    adr_generator.py 非交互模式必须有 --title，而 generate-adr 过去只传
    --pr，导致自动化下必然失败（无标题 -> 非交互无法提问 -> 退出码 1）。
    先问 gh，再退到 git commit subject，最后才用通用标题。
    """
    if ref.isdigit():
        gh = shutil.which("gh")
        if gh:
            try:
                out = subprocess.run(
                    [gh, "pr", "view", ref, "--json", "title", "-q", ".title"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if out.returncode == 0 and out.stdout.strip():
                    return out.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                pass
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%s", ref],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return f"架构决策记录（来源 {ref}）"


def generate_adr() -> int:
    """从 PR 生成 ADR"""
    print_section("ADR 生成")
    ref = _pr_ref()
    code, output = run_command(
        [
            sys.executable,
            "tools/scripts/adr_generator.py",
            "--pr",
            ref,
            "--title",
            _resolve_title(ref),
            "--brief",
            f"依据 PR / commit {ref} 归档架构决策",
        ]
    )
    print_check("ADR 生成", code == 0, output)
    if code != 0:
        print(output)
    return code


def leaderboard() -> int:
    """贡献者排行榜"""
    print_section("贡献者排行榜")
    code, output = run_command([sys.executable, "tools/scripts/contributor_dashboard.py", "--leaderboard"])
    print_check("排行榜", code == 0, output)
    if code != 0:
        print(output)
    return code


def stats() -> int:
    """查看社区统计"""
    print_section("社区统计")
    case_dir = get_project_root() / "docs" / "case-studies"
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
        print("Actions: triage, validate, stats, generate-adr, leaderboard")
        sys.exit(1)

    action = sys.argv[1]

    action_map = {
        "generate-adr": generate_adr,
        "leaderboard": leaderboard,
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
