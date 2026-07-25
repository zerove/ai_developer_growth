from __future__ import annotations

import subprocess
import sys
from pathlib import Path

def _get_git_changed_files(since: str, cwd: Path | None = None) -> list[Path]:
    """Get list of files changed since a git reference.

    Args:
        since: Git reference (HEAD~1, commit hash, branch, etc.)
        cwd: Working directory (defaults to current)

    Returns:
        List of changed file paths
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACM", since],
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=10,
        )
        if result.returncode != 0:
            print(f"Warning: git diff failed: {result.stderr}", file=sys.stderr)
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                fp = Path(line.strip())
                if fp.is_file():
                    files.append(fp)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: git command failed: {e}", file=sys.stderr)
        return []


def _get_unstaged_files(cwd: Path | None = None) -> list[Path]:
    """Get list of unstaged changed files."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=10,
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                fp = Path(line.strip())
                if fp.is_file():
                    files.append(fp)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_staged_files(cwd: Path | None = None) -> list[Path]:
    """Get list of staged files."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=10,
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                fp = Path(line.strip())
                if fp.is_file():
                    files.append(fp)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
