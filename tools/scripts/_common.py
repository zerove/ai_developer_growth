"""Shared utilities for AI Language Rules tools.

Eliminates code duplication across rule_marketplace.py, generate_fixes.py,
rule_author.py, rule_visualize.py, validate_rule_tests.py, and others.

Usage:
    from _common import rules_dir, framework_dir, EXTENSION_MAP, detect_language
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────
# Path helpers
# ──────────────────────────────────────────────────────────


def rules_dir() -> Path:
    """Return the ai-dev-framework directory."""
    return Path(__file__).parent.parent.parent / "ai-dev-framework"


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
    """Standard error handler with consistent formatting."""
    msg = f"Error: {e}" if not script else f"Error in {script}: {e}"
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
            return yaml.safe_load(f)
    except Exception:
        return None


def save_yaml(filepath: Path, data: dict[str, Any]) -> None:
    """Save data to YAML file."""
    import yaml
    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ──────────────────────────────────────────────────────────
# Supported file filtering
# ──────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = set(EXTENSION_MAP.keys())


def filter_supported_files(files: list[Path]) -> list[Path]:
    """Filter to only files supported by the rules engine."""
    return [f for f in files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
