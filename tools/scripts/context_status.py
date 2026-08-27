"""CONTEXT.md 拆分工具: 把滚动日志 + 实时指标分离, 还原"项目快照"语义。

模式:
  status     输出项目实时快照(测试数/覆盖率/最新 tag/最近 5 个 commit)
  split      一次性拆分 CONTEXT.md → PROJECT-STATUS.md(快照) + CONTEXT.md(精简)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from tools.scripts._common import get_project_root

ROLLING_SECTION_RE = re.compile(
    r"^## 更新记录:.*?(?=^## [^\s]|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _git(args: list[str]) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=str(get_project_root()))
    return r.stdout.strip()


def _print_version(root: Path) -> None:
    """输出当前版本(从 pyproject.toml)."""
    try:
        version = re.search(
            r'^version\s*=\s*"([^"]+)"', (root / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE
        )
        print(f"  📦 Version : {version.group(1) if version else '?'}")
    except OSError:
        pass


def _print_latest_tag() -> None:
    """输出最新 tag."""
    try:
        tag = _git(["describe", "--tags", "--abbrev=0"])
        print(f"  🏷  Latest tag : {tag}")
    except subprocess.CalledProcessError:
        print("  🏷  Latest tag : (none)")


def _print_recent_commits() -> None:
    """输出最近 5 个 commit."""
    print("\n  📝 Recent commits:")
    for line in _git(["log", "--oneline", "-5"]).splitlines():
        print(f"     {line}")


def _print_count(label: str, count: int) -> None:
    """输出计数行."""
    print(f"  {label} : {count}")


def _print_last_commit_time() -> None:
    """输出上次 commit 日期."""
    try:
        last_time = _git(["log", "-1", "--format=%cd", "--date=short"])
        print(f"  ⏱  Last commit : {last_time}")
    except subprocess.CalledProcessError:
        pass


def cmd_status() -> int:
    """Output real-time project snapshot to stdout."""
    root = get_project_root()
    print("═" * 60)
    print(" Project Status Snapshot")
    print("═" * 60)

    _print_version(root)
    _print_latest_tag()
    _print_recent_commits()

    tests_dir = root / "tests"
    test_count = sum(1 for _ in tests_dir.rglob("test_*.py")) if tests_dir.exists() else 0
    print(f"\n  🧪 Test files : {test_count}")

    scripts_dir = root / "tools" / "scripts"
    script_count = sum(1 for _ in scripts_dir.glob("*.py") if not _.name.startswith("_")) if scripts_dir.exists() else 0
    print(f"  🛠  Tool scripts : {script_count}")

    _print_last_commit_time()

    docs_dir = root / "docs"
    doc_count = sum(1 for _ in docs_dir.rglob("*.md")) if docs_dir.exists() else 0
    print(f"  📚 Doc files : {doc_count}")
    return 0


def cmd_split(args: argparse.Namespace) -> int:
    """一次性拆分 CONTEXT.md: 滚动日志归档到 CHANGELOG, 主体保留精简版。"""

    root = get_project_root()
    context_path = root / "CONTEXT.md"
    if not context_path.exists():
        print("❌ CONTEXT.md not found")
        return 1

    content = context_path.read_text(encoding="utf-8")

    # 抽取所有"## 更新记录"块
    rolling_blocks = ROLLING_SECTION_RE.findall(content)
    kept_blocks_count = int(getattr(args, "keep", 5))
    keep = rolling_blocks[:kept_blocks_count]
    archive = rolling_blocks[kept_blocks_count:]

    # 重建 CONTEXT.md
    new_content = (
        "# CONTEXT.md — 项目核心状态(自动滚动日志已拆分)\n\n"
        "> 本文件保留项目级核心信息(技术栈/治理/项目目标)。\n"
        "> 历史滚动日志见 CHANGELOG.md 与 git log。\n"
        "> 实时快照: `python tools/scripts/context_status.py status`\n\n"
        "## 项目核心\n\n"
        "**项目**: AI Developer Growth(ADG) — 开源 AI 时代开发者成长知识库。\n\n"
        "**治理工具链**: ruff + mypy + pytest (3493+ tests) + ADG 自研 hooks。\n\n"
        "**覆盖率**: 见 `make test-cov` 或 `make cov-status`。\n\n"
        "**变更追溯**: 见 CHANGELOG.md / git log / ADR.md。\n"
    )
    if keep:
        new_content += "\n## 最近 5 次自动同步\n" + "\n---\n".join(keep)

    context_path.write_text(new_content, encoding="utf-8")
    print(f"✓ CONTEXT.md 精简: 保留 {len(keep)} 条滚动日志, 归档 {len(archive)} 条")

    if archive:
        # 追加到 CHANGELOG 的"自动滚动日志归档"区
        cl_path = root / "CHANGELOG.md"
        cl = cl_path.read_text(encoding="utf-8") if cl_path.exists() else ""
        archive_block = "\n\n## 滚动日志归档 (from CONTEXT.md, auto-trimmed)\n\n" + "\n---\n".join(archive)
        if "滚动日志归档" not in cl:
            cl_path.write_text(cl + archive_block, encoding="utf-8")
            print(f"✓ 归档 {len(archive)} 条滚动日志到 CHANGELOG.md")
    return 0


def main() -> int:
    import argparse as _ap

    parser = _ap.ArgumentParser(prog="context-status", description="Project status / CONTEXT split")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Print real-time project snapshot").set_defaults(_func=lambda a: cmd_status())
    p_split = sub.add_parser("split", help="One-time CONTEXT.md split: rolling logs → CHANGELOG")
    p_split.add_argument("--keep", default="5", help="Number of recent rolling entries to keep in CONTEXT.md")
    p_split.set_defaults(_func=cmd_split)

    args = parser.parse_args()
    if args.command == "split":
        return cmd_split(args)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
