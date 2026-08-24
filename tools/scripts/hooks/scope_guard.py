"""Small-Batch / Large-Diff Scope Guard Hook

Enforces small-batch development (DORA AI countermeasure against instability):
Inspects git diff and warns or blocks if line changes or file count exceed safe thresholds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.scripts._common import get_project_root


class ScopeGuardHook:
    def __init__(self, max_lines: int = 300, max_files: int = 5, root_dir: Path | None = None):
        self.max_lines = max_lines
        self.max_files = max_files
        self.root_dir = root_dir or get_project_root()

    def check_git_diff(self) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["git", "diff", "--cached", "--numstat"],
                capture_output=True,
                text=True,
                cwd=self.root_dir,
            )
            if res.returncode != 0:
                return (
                    True,
                    "Git diff check skipped (not a git repo or no staged changes).",
                )

            lines = res.stdout.strip().splitlines()
            total_added = 0
            total_deleted = 0
            file_count = len(lines)

            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    total_added += int(parts[0])
                    total_deleted += int(parts[1])

            total_changed = total_added + total_deleted

            if file_count > self.max_files or total_changed > self.max_lines:
                msg = f"Scope Guard Warning: Large diff detected ({file_count} files, {total_changed} lines changed). Exceeds recommended small-batch limits ({self.max_files} files, {self.max_lines} lines). Consider splitting commit."
                return False, msg

            return (
                True,
                f"Scope check passed: {file_count} files, {total_changed} lines changed.",
            )
        except Exception as e:
            return True, f"Scope check skipped due to error: {e}"


if __name__ == "__main__":
    guard = ScopeGuardHook()
    passed, msg = guard.check_git_diff()
    print(msg)
