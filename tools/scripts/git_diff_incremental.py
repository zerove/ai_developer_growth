#!/usr/bin/env python3
"""Incremental validation with git diff integration (#7).

Only validates files that have changed since last commit or a specified ref.

Usage:
    python tools/scripts/validate_language_rules.py --all --incremental
    python tools/scripts/validate_language_rules.py --all --git-diff HEAD~1
    python tools/scripts/validate_language_rules.py --all --git-diff main
    python tools/scripts/validate_language_rules.py --lang python --git-diff HEAD
"""

from __future__ import annotations

import json

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from tools.scripts._common import filter_supported_files, handle_error  # noqa: E402


def get_git_changed_files(ref: str = "HEAD", repo_dir: str | None = None) -> list[Path]:
    """Get files changed since a git ref.

    Args:
        ref: Git ref to compare against (commit, branch, tag)
        repo_dir: Repository root directory

    Returns:
        List of changed file paths
    """
    try:
        cmd = ["git", "diff", "--name-only", ref]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_dir,
            timeout=30,
        )
        if result.returncode != 0:
            # Try diff with HEAD if ref not found
            cmd = ["git", "diff", "--name-only", "HEAD"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_dir,
                timeout=30,
            )

        files = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                path = Path(line) if repo_dir is None else Path(repo_dir) / line
                if path.exists():
                    files.append(path)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_git_untracked_files(repo_dir: str | None = None) -> list[Path]:
    """Get untracked files in the repository."""
    try:
        cmd = ["git", "ls-files", "--others", "--exclude-standard"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_dir,
            timeout=30,
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                path = Path(line) if repo_dir is None else Path(repo_dir) / line
                if path.exists():
                    files.append(path)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_git_staged_files(repo_dir: str | None = None) -> list[Path]:
    """Get staged (cached) files."""
    try:
        cmd = ["git", "diff", "--cached", "--name-only"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_dir,
            timeout=30,
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                path = Path(line) if repo_dir is None else Path(repo_dir) / line
                if path.exists():
                    files.append(path)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_incremental_files(
    repo_dir: str | None = None,
    ref: str | None = None,
) -> list[Path]:
    """Get files that need validation (changed + untracked + staged).

    If ref is provided, get files changed since that ref.
    Otherwise, get untracked + staged files (pre-commit mode).
    """
    files: set[Path] = set()

    if ref:
        # Post-commit mode: validate files changed since ref
        files.update(get_git_changed_files(ref, repo_dir))
    else:
        # Pre-commit mode: validate staged + untracked files
        files.update(get_git_staged_files(repo_dir))
        files.update(get_git_untracked_files(repo_dir))

    return sorted(files)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Get files changed by git diff")
    parser.add_argument("--ref", type=str, default=None, help="Git ref to compare against")
    parser.add_argument("--repo-dir", type=str, default=None, help="Repository root")
    parser.add_argument(
        "--supported-only",
        action="store_true",
        help="Filter to supported languages only",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Detailed output")
    args = parser.parse_args()

    try:
        files = get_incremental_files(args.repo_dir, args.ref)

        if args.supported_only:
            files = filter_supported_files(files)

        if args.json_output:
            print(json.dumps([str(f) for f in files], indent=2))
        else:
            for f in files:
                print(f)

        if args.verbose:
            print(f"\n{len(files)} files changed", file=sys.stderr)
        return 0
    except Exception as e:
        handle_error(e, script="git_diff_incremental")
        return 1


if __name__ == "__main__":
    sys.exit(main())
