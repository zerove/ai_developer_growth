"""Shared utilities for AI Language Rules tools and jcode Skills.

Eliminates code duplication across:
- rule_marketplace.py, generate_fixes.py, rule_author.py, rule_visualize.py,
  validate_rule_tests.py, validate_language_rules.py
- .jcode/scripts/*.py (skill runners)

Usage:
    from _common import (
        # Path helpers
        rules_dir, framework_dir, get_project_root,
        # Extension map
        EXTENSION_MAP, detect_language,
        # Command execution
        run_command,
        # Hashing
        file_hash,
        # Error handling
        handle_error, safe_import,
        # YAML
        load_yaml, save_yaml,
        # Output formatting
        print_check, print_section,
        # File filtering
        filter_supported_files,
    )
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────
# Path helpers
# ──────────────────────────────────────────────────────────


def get_project_root() -> Path:
    """Get project root directory (works from tools/scripts/ or .jcode/scripts/)."""
    return Path(__file__).parent.parent.parent


def rules_dir() -> Path:
    """Return the ai-dev-framework directory."""
    return get_project_root() / "ai-dev-framework"


def framework_dir() -> Path:
    """Alias for rules_dir (used by marketplace)."""
    return rules_dir()


# ──────────────────────────────────────────────────────────
# Extension map (single source of truth)
# ──────────────────────────────────────────────────────────

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".fs": "csharp",
    ".vb": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".scala": "scala",
    ".dart": "dart",
    ".lua": "lua",
    ".hs": "haskell",
    ".lhs": "haskell",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".r": "r",
    ".R": "r",
    ".pl": "perl",
    ".pm": "perl",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".zig": "zig",
    ".c": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".m": "matlab",
    ".f90": "fortran",
    ".f95": "fortran",
    ".f": "fortran",
    ".for": "fortran",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".asm": "assembly",
    ".s": "assembly",
    ".S": "assembly",
    ".nasm": "assembly",
}


def detect_language(filepath: Path) -> str | None:
    """Detect language from file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


# ──────────────────────────────────────────────────────────
# Command execution
# ──────────────────────────────────────────────────────────


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run command and return (exit_code, combined_output)."""
    if cwd is None:
        cwd = get_project_root()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout + result.stderr


# ──────────────────────────────────────────────────────────
# Hashing
# ──────────────────────────────────────────────────────────


def file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of file content (truncated to 16 chars)."""
    try:
        h = hashlib.sha256()
        h.update(filepath.read_bytes())
        return h.hexdigest()[:16]
    except (OSError, ValueError):
        return ""


# ──────────────────────────────────────────────────────────
# Error handling
# ──────────────────────────────────────────────────────────


def handle_error(e: Exception, script: str = "", exit_code: int = 1) -> None:
    """统一错误处理器，使用中文格式。"""
    msg = f"错误: {e}" if not script else f"{script} 出错: {e}"
    print(msg, file=sys.stderr)
    sys.exit(exit_code)


def safe_import(module_name: str, package: str = "") -> Any | None:
    """Safely import a module, returning None if not available."""
    try:
        if package:
            from importlib import import_module

            return import_module(f"{package}.{module_name}")
        return __import__(module_name)
    except ImportError:
        return None


# ──────────────────────────────────────────────────────────
# YAML loading
# ──────────────────────────────────────────────────────────


def load_yaml(filepath: Path) -> dict[str, Any] | None:
    """Load YAML file safely."""
    try:
        import yaml

        with open(filepath) as f:
            result: dict[str, Any] | None = yaml.safe_load(f)
            return result
    except Exception:
        return None


def save_yaml(filepath: Path, data: dict[str, Any]) -> None:
    """Save data to YAML file."""
    import yaml

    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ──────────────────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────────────────


def print_check(name: str, passed: bool, output: str = "") -> None:
    """输出检查结果，使用中文格式。"""
    label = "通过" if passed else "失败"
    icon = "✅" if passed else "❌"
    print(f"{icon} [{label}] {name}")
    if output and not passed:
        for line in output.strip().split("\n")[:20]:
            print(f"  {line}")


def print_section(title: str) -> None:
    """打印中文分隔线和标题。"""
    line = "—" * 40
    print(f"\n{line}")
    print(f"  {title}")
    print(line)


# ──────────────────────────────────────────────────────────
# Supported file filtering
# ──────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = set(EXTENSION_MAP.keys())


def filter_supported_files(files: list[Path]) -> list[Path]:
    """Filter to only files supported by the rules engine."""
    return [f for f in files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
