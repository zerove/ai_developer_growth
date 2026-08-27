from __future__ import annotations

import argparse
import sys

from ._shared import (
    _DEFAULT_PRE_COMMIT_HOOK,
    _DEFAULT_PRE_PUSH_HOOK,
    Path,
)


def cmd_install_hooks(args: argparse.Namespace) -> int:
    """Install pre-commit hook into a project."""
    target = Path(args.path).resolve()
    git_dir = target / ".git"

    if not git_dir.exists():
        print(f"Error: Not a git repository: {target}", file=sys.stderr)
        return 1

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    # Install pre-push hook if requested
    if getattr(args, "pre_push", False):
        hook_path = hooks_dir / "pre-push"
        adg_hook_source = Path.home() / ".config" / "adg" / "hooks" / "pre-push"

        if adg_hook_source.exists():
            hook_path.write_text(adg_hook_source.read_text())
        else:
            hook_path.write_text(_DEFAULT_PRE_PUSH_HOOK)

        hook_path.chmod(0o755)
        print(f"✅ ADG pre-push hook installed: {hook_path}")
        print("   Run 'adg check .' to test manually")
        return 0

    # Default: install pre-commit hook
    hook_path = hooks_dir / "pre-commit"
    adg_hook_source = Path.home() / ".config" / "adg" / "hooks" / "pre-commit"

    # Try to copy from installed hooks first
    if adg_hook_source.exists():
        hook_path.write_text(adg_hook_source.read_text())
    else:
        # Write default hook
        hook_path.write_text(_DEFAULT_PRE_COMMIT_HOOK)

    hook_path.chmod(0o755)
    print(f"✅ ADG pre-commit hook installed: {hook_path}")
    print("   Run 'adg check .' to test manually")
    return 0
