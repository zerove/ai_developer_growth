#!/usr/bin/env python3
"""Semantic Commit Generator: analyzes staged changes and generates Conventional Commits messages."""

from __future__ import annotations

import argparse
import subprocess
import sys


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def generate_commit_message(files: list[str]) -> str:
    """Generate conventional commit message based on staged files.

    V2.21 P5-1 拆分: 抽 _detect_file_types 收口 4 个 any 类别判定,
    _select_commit_template 收口 5 档 if 分支选择,
    主函数仅委托.
    """
    if not files:
        return "chore: update repository files"

    file_types = _detect_file_types(files)
    return _select_commit_template(file_types)


def _detect_file_types(files: list[str]) -> dict[str, bool]:
    """从 files 检测 4 类类别标志 (模块级 helper).

    Args:
        files: 文件路径列表

    Returns:
        {has_docs, has_tests, has_ci, has_tools} dict
    """
    return {
        "has_docs": any(f.endswith(".md") or "docs/" in f for f in files),
        "has_tests": any("test" in f for f in files),
        "has_ci": any(".github/" in f or "ci" in f for f in files),
        "has_tools": any("tools/" in f for f in files),
    }


def _select_commit_template(file_types: dict[str, bool]) -> str:
    """根据 file_types 选择 commit 模板 (模块级 helper).

    Args:
        file_types: 4 类别标志 dict

    Returns:
        commit 消息字符串
    """
    has_docs = file_types["has_docs"]
    has_tests = file_types["has_tests"]
    has_ci = file_types["has_ci"]
    has_tools = file_types["has_tools"]

    if has_docs and not has_tools and not has_tests:
        return "docs: update knowledge base and documentation"
    if has_tests and not has_tools:
        return "test: add or update test suites"
    if has_ci:
        return "ci: update GitHub Actions and workflows"
    if has_tools:
        return "feat(tools): enhance automation scripts and CLI tooling"
    return "refactor: update implementation and architecture components"


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantic Commit Generator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated commit message without committing",
    )
    args = parser.parse_args()

    files = get_staged_files()
    msg = generate_commit_message(files)

    if args.dry_run:
        print(msg)
    else:
        try:
            subprocess.run(["git", "commit", "-m", msg], check=True)
            print(f"✅ Committed successfully with message: '{msg}'")
        except subprocess.SubprocessError:
            print(f"❌ Error: git commit failed. Suggested message: '{msg}'")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
