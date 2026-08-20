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
    """Generate conventional commit message based on staged files."""
    if not files:
        return "chore: update repository files"

    has_docs = any(f.endswith(".md") or "docs/" in f for f in files)
    has_tests = any("test" in f for f in files)
    has_ci = any(".github/" in f or "ci" in f for f in files)
    has_tools = any("tools/" in f for f in files)

    # Determine scope and type
    if has_docs and not has_tools and not has_tests:
        return "docs: update knowledge base and documentation"
    if has_tests and not has_tools:
        return "test: add or update test suites"
    if has_ci:
        return "ci: update GitHub Actions and workflows"
    if has_tools:
        return "feat(tools): enhance automation scripts and CLI tooling"

    # Default
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
