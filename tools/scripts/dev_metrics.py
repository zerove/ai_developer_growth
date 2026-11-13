#!/usr/bin/env python3
"""项目开发过程自我度量（P2-1：用数据回答"方法论对自己是否有效"）。

从 git 历史聚合：
- 提交总量与时间跨度
- conventional commit 格式合规率
- 钩子相关修复提交数（含 "ruff format"/"mypy"/"格式化" 关键词）
- 月度提交分布

用法: python -m tools.scripts.dev_metrics [--since 2026-01-01]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

CONVENTIONAL = re.compile(r"^(feat|fix|refactor|docs|test|chore|style|perf|build|ci)(\(.+\))?: .+")
HOOK_FIX_KEYWORDS = ("ruff", "mypy", "格式化", "lint", "钩子", "hook")


def git_log_since(repo: Path, since: str | None) -> list[str]:
    """返回 subject 行列表。"""
    cmd = ["git", "-C", str(repo), "log", "--pretty=%s"]
    if since:
        cmd.append(f"--since={since}")
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def first_commit_date(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "--reverse", "--pretty=%ad", "--date=short"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line for line in out.stdout.splitlines() if line.strip()]
    return lines[0] if lines else "n/a"


def compute(subjects: list[str]) -> dict[str, object]:
    """核心统计（独立函数便于测试）。"""
    total = len(subjects)
    conventional = sum(1 for s in subjects if CONVENTIONAL.match(s))
    hook_fixes = sum(1 for s in subjects if any(k in s.lower() for k in HOOK_FIX_KEYWORDS))
    return {
        "total_commits": total,
        "conventional_count": conventional,
        "conventional_rate": round(conventional / total * 100, 1) if total else 0.0,
        "hook_fix_commits": hook_fixes,
    }


def monthly_distribution(repo: Path) -> list[tuple[str, int]]:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "--pretty=%ad", "--date=format:%Y-%m"],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(Counter(line for line in out.stdout.splitlines() if line.strip()).items())


def render(metrics: dict[str, object], repo: Path) -> str:
    start = first_commit_date(repo)
    lines = [
        "=" * 50,
        "ADG 开发过程自我度量",
        f"首次提交: {start}",
        "=" * 50,
        f"提交总数: {metrics['total_commits']}",
        f"conventional 格式: {metrics['conventional_count']} ({metrics['conventional_rate']}%)",
        f"钩子/工具链修复类提交: {metrics['hook_fix_commits']}",
        "-" * 50,
        "月度分布:",
    ]
    for month, count in monthly_distribution(repo):
        bar = "#" * min(count, 50)
        lines.append(f"  {month}  {count:4d}  {bar}")
    lines.append("=" * 50)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="开发过程自我度量")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent.parent)
    parser.add_argument("--since", default=None)
    args = parser.parse_args()

    subjects = git_log_since(args.repo, args.since)
    metrics = compute(subjects)
    print(render(metrics, args.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
