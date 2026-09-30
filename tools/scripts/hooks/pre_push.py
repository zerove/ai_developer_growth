"""Pre-push hook: checks unpushed commits before allowing push.

Usage:
    # Install as git pre-push hook:
    cp tools/scripts/hooks/pre_push.py .git/hooks/pre-push && chmod +x .git/hooks/pre-push

    # Or via hooks_runner:
    hooks_runner.py install-hooks --pre-push
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

# 视为代码文件的扩展名
CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".rs",
        ".java",
        ".cs",
        ".go",
        ".cpp",
    }
)


def load_skip_patterns() -> list[str]:
    """Load skip patterns from .adg/config.yml (repo-relative globs).

    Keeps the pre-push hook consistent with the adg CLI: files matching
    skip_patterns (e.g. tests/, demo files) are not validated.
    """
    config_path = Path(".adg") / "config.yml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        patterns = config.get("skip_patterns", []) if isinstance(config, dict) else []
        return [p for p in patterns if isinstance(p, str)]
    except (OSError, yaml.YAMLError):
        return []


def _matches_skip_pattern(filepath: Path, patterns: list[str]) -> bool:
    """Check if filepath matches any skip pattern.

    Patterns like ``**/tests/**/*.py`` require a leading slash to match,
    so we test the repo-relative path, the absolute path, and the basename
    (mirrors adg CLI behavior which matches absolute rglob paths).
    """
    candidates = (str(filepath), str(filepath.resolve()), filepath.name)
    return any(Path(c).match(p) for p in patterns for c in candidates)


def get_unpushed_commits(remote: str = "origin", branch: str | None = None) -> list[str]:
    """Get list of commit hashes that haven't been pushed to remote.

    Args:
        remote: Remote name.
        branch: Branch name (auto-detected if None).

    Returns:
        List of short commit hashes.
    """
    if branch is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            branch = result.stdout.strip()
        except Exception:
            return []

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"{remote}/{branch}..HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Remote branch doesn't exist yet - all commits are unpushed
            result = subprocess.run(
                ["git", "log", "--oneline"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [line.split()[0] for line in lines if line.split()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_changed_files_in_unpushed_commits() -> list[Path]:
    """Get files changed in unpushed commits."""
    commits = get_unpushed_commits()
    if not commits:
        return []

    try:
        oldest = commits[-1]
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{oldest}^..HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(f"Failed to get changed files in unpushed commits: {e}")
        return []


def _check_code_files(code_files: list[Path]) -> bool:
    """Run lint and format checks on Python files."""
    from tools.scripts.hooks.basic_checks import run_format_files, run_lint_files

    py_files = [str(f) for f in code_files if f.suffix == ".py"]
    all_passed = True

    if py_files:
        print("\n🔍 Running lint checks...")
        lint_passed, lint_out = run_lint_files(py_files)
        if not lint_passed:
            print(f"❌ Lint errors:\n{lint_out}")
            all_passed = False

        print("🔍 Running format checks...")
        fmt_passed, fmt_out = run_format_files(py_files)
        if not fmt_passed:
            print(f"❌ Format errors:\n{fmt_out}")
            all_passed = False

    return all_passed


def _check_language_rules(code_files: list[Path]) -> tuple[bool, list[Path]]:
    """Run language rules checks on code files."""
    from tools.scripts.validate_language_rules import (
        detect_language_from_file,
        validate_file,
    )

    skip_patterns = load_skip_patterns()
    skipped: list[Path] = []
    all_passed = True

    print("🔍 Running language rules...")
    for filepath in code_files:
        if _matches_skip_pattern(filepath, skip_patterns):
            skipped.append(filepath)
            continue
        lang = detect_language_from_file(filepath)
        if lang:
            result = validate_file(filepath, lang)
            if not result.passed:
                print(f"❌ {filepath}: {len(result.issues)} violations")
                all_passed = False

    return all_passed, skipped


def _collect_changed_code_files(changed_files: list[Path]) -> list[Path]:
    """筛选出存在且为代码文件的变更。"""
    return [f for f in changed_files if f.suffix in CODE_FILE_EXTENSIONS and f.exists()]


def _run_all_checks(code_files: list[Path]) -> tuple[bool, list[Path]]:
    """执行 lint/格式与语言规则检查; 返回 (是否全部通过, 跳过文件)。"""
    all_passed = _check_code_files(code_files)
    lang_passed, skipped = _check_language_rules(code_files)
    return (lang_passed and all_passed), skipped


def run_pre_push_check() -> int:
    """Run checks on unpushed commits. Returns exit code (0 = allow push)."""
    commits = get_unpushed_commits()
    if not commits:
        print("✅ No unpushed commits. Push allowed.")
        return 0

    print(f"🔍 Checking {len(commits)} unpushed commit(s)...")

    code_files = _collect_changed_code_files(get_changed_files_in_unpushed_commits())
    if not code_files:
        print("✅ No code files changed. Push allowed.")
        return 0

    print(f"📄 {len(code_files)} code file(s) changed:")
    for f in code_files:
        print(f"   {f}")

    # Run checks
    all_passed, skipped = _run_all_checks(code_files)

    if skipped:
        print(f"⏭️  Skipped {len(skipped)} file(s) matching skip_patterns: {', '.join(str(f) for f in skipped)}")

    if all_passed:
        print("\n✅ All checks passed. Push allowed.")
        return 0
    print("\n❌ Checks failed. Fix issues before pushing.")
    print("   Use: git commit --no-verify to bypass (not recommended)")
    return 1


def install_pre_push_hook() -> bool:
    """Install the full pre-push gate from the tracked source into .git/hooks/.

    The hook body lives in ``.jcode/hooks/pre-push`` (version-controlled)
    because ``.git/`` is not distributed with the repository. Installing a
    hand-written wrapper here would silently downgrade the gate to the
    unpushed-commits check alone, losing lint/typecheck/test/quality-gate.

    Both the source and the target are resolved against the current working
    directory, so the function stays testable and installs into whichever
    repository the developer is standing in.

    Returns:
        True if successful.
    """
    repo_root = Path.cwd()
    source = repo_root / ".jcode" / "hooks" / "pre-push"
    if not source.exists():
        print(f"Error: tracked hook source not found: {source}")
        return False

    hooks_dir = repo_root / ".git" / "hooks"
    if not hooks_dir.exists():
        print("Error: Not in a git repository (.git/hooks not found)")
        return False

    target = hooks_dir / "pre-push"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    target.chmod(0o755)
    print(f"✅ Pre-push hook installed at {target}")
    print(f"   (source: {source.relative_to(repo_root)})")
    return True


if __name__ == "__main__":
    sys.exit(run_pre_push_check())
