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
        EXTENSION_MAP, detect_language, EXCLUDE_DIRS,
        # Command execution
        run_command,
        # Hashing
        file_hash, file_hash_full,
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

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.scripts.rules_engine.ast_nodes import _TreeNode

# ----------------------------------------------------------
# Path helpers
# ----------------------------------------------------------


def get_project_root() -> Path:
    """Get project root directory (works from tools/scripts/ or .jcode/scripts/)."""
    return Path(__file__).parent.parent.parent


def rules_dir() -> Path:
    """Return the ai-dev-framework directory.

    Search order (first found wins):
    1. Project local: {project_root}/ai-dev-framework/
    2. Environment variable: $JCODE_GOVERNANCE_DIR
    3. jcode user-wide install: ~/.jcode/governance/ai-dev-framework/
    4. User config: ~/.config/adg/framework/
    5. Fallback: {project_root}/ai-dev-framework/ (original)
    """
    project_path = get_project_root() / "ai-dev-framework"

    # 1. Local project
    if project_path.exists():
        return project_path

    # 2. Env var
    env_path = Path(os.environ.get("JCODE_GOVERNANCE_DIR", ""))
    if env_path and env_path.exists():
        return env_path

    # 3. jcode user-wide install
    jcode_path = Path.home() / ".jcode" / "governance" / "ai-dev-framework"
    if jcode_path.exists():
        return jcode_path

    # 4. User config
    config_path = Path.home() / ".config" / "adg" / "framework"
    if config_path.exists():
        return config_path

    # 5. Fallback
    return project_path


def framework_dir() -> Path:
    """Alias for rules_dir (used by marketplace)."""
    return rules_dir()


# ----------------------------------------------------------
# Argument helpers
# ----------------------------------------------------------


def discover_languages(args: argparse.Namespace) -> list[str]:
    """Discover languages to process based on args.

    Public version of `_discover_languages` from validate_rule_tests.py +
    generate_fixes.py. Both files used identical 5-line implementations.
    """
    if args.all:
        langs_dir = rules_dir() / "languages"
        return sorted(d.name for d in langs_dir.iterdir() if d.is_dir() and (d / "rules.d").exists())
    return [args.lang]


# ----------------------------------------------------------
# Extension map (single source of truth)
# ----------------------------------------------------------

# 排除目录（通用配置）
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
}

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
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
    ".ex": "elixir",
    ".exs": "elixir",
}


def detect_language(filepath: Path) -> str | None:
    """Detect language from file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


# 别名: detect_language.py / validators/pipeline.py 中的 detect_language_from_file
# 与 detect_language 逻辑完全一致 (Phase 34 统一)
detect_language_from_file = detect_language


# Canonical rule-ID prefixes used by ai-dev-framework/languages/*/rules.d.
# Keep this aligned with the YAML IDs; language[:2] is not reliable
# (rust -> ru, java/javascript -> ja, ruby -> ru, typescript -> ty).
RULE_ID_PREFIXES: dict[str, str] = {
    "assembly": "asm",
    "clojure": "clj",
    "cpp": "cpp",
    "csharp": "cs",
    "dart": "dt",
    "elixir": "ex",
    "fortran": "for",
    "go": "go",
    "graphql": "gql",
    "haskell": "hs",
    "java": "java",
    "javascript": "js",
    "kotlin": "kt",
    "lua": "lua",
    "matlab": "mcl",
    "perl": "pl",
    "php": "php",
    "powershell": "ps",
    "python": "py",
    "r": "r",
    "ruby": "rb",
    "rust": "rs",
    "scala": "sc",
    "swift": "sw",
    "typescript": "ts",
    "zig": "zig",
}


def rule_id_prefix(language: str) -> str:
    """Return the canonical rule-ID prefix for a language.

    Unknown languages fall back to their first two characters, preserving the
    previous best-effort behavior for callers outside the supported set.
    """
    normalized = language.strip().lower()
    return RULE_ID_PREFIXES.get(normalized, normalized[:2])


# ----------------------------------------------------------
# Command execution
# ----------------------------------------------------------


def run_command(cmd: list[str], cwd: Path | None = None, timeout: float | None = None) -> tuple[int, str]:
    """Run command and return (exit_code, combined_output)."""
    if cwd is None:
        cwd = get_project_root()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"命令超时 ({timeout}s): {' '.join(cmd)}"
    return result.returncode, result.stdout + result.stderr


# ----------------------------------------------------------
# Hashing
# ----------------------------------------------------------


def file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of file content (truncated to 16 chars for cache keys)."""
    try:
        h = hashlib.sha256()
        h.update(filepath.read_bytes())
        return h.hexdigest()[:16]
    except (OSError, ValueError):
        return ""


def file_hash_full(filepath: Path) -> str:
    """Compute full SHA256 hash of file content (64 chars for content comparison)."""
    try:
        h = hashlib.sha256()
        h.update(filepath.read_bytes())
        return h.hexdigest()
    except (OSError, ValueError):
        return ""


# ----------------------------------------------------------
# Error handling
# ----------------------------------------------------------


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


# ----------------------------------------------------------
# YAML loading
# ----------------------------------------------------------


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


# ----------------------------------------------------------
# Output formatting
# ----------------------------------------------------------


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


# ----------------------------------------------------------
# Supported file filtering
# ----------------------------------------------------------

SUPPORTED_EXTENSIONS = set(EXTENSION_MAP.keys())


def filter_supported_files(files: list[Path]) -> list[Path]:
    """Filter to only files supported by the rules engine."""
    return [f for f in files if f.suffix.lower() in SUPPORTED_EXTENSIONS]


def walk_files(root: Path, *, skip_dir: Callable[[str], bool] | None = None) -> list[Path]:
    """递归枚举 root 下的文件，并在遍历时就地剪枝跳过目录。

    Path.rglob 无法剪枝：进入 .venv/.git/node_modules 后才逐条过滤，仓库根
    实测会多枚举两万余条路径。os.walk 的 dirnames 原地切片可在进入前剪掉，
    这是 adg_cli / rules_engine / ai_quality_gate 三处文件发现的唯一实现。

    Args:
        root: 扫描根目录
        skip_dir: 目录名判定函数，返回 True 则不进入该目录

    Returns:
        文件路径列表（不含目录），顺序与 os.walk 一致，未排序。
    """
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if skip_dir is not None:
            dirnames[:] = [name for name in dirnames if not skip_dir(name)]
        dirpath_obj = Path(dirpath)
        files.extend(dirpath_obj / name for name in filenames)
    return files


# ----------------------------------------------------------
# Tree node helpers (rules_engine parsers, Phase 34)
# ----------------------------------------------------------


def child_by_type(node: _TreeNode, node_type: str) -> _TreeNode | None:
    """Return first direct child of the given type."""
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def find_first(node: _TreeNode, node_type: str) -> _TreeNode | None:
    """Return first node of the given type via DFS (self inclusive)."""
    if node.type == node_type:
        return node
    for child in node.children:
        found = find_first(child, node_type)
        if found:
            return found
    return None


def find_first_at_depth(node: _TreeNode, node_type: str, max_depth: int) -> _TreeNode | None:
    """Return first node of the given type via DFS, bounded by max_depth."""
    if node.type == node_type:
        return node
    if max_depth <= 0:
        return None
    for child in node.children:
        found = find_first_at_depth(child, node_type, max_depth - 1)
        if found:
            return found
    return None


def node_text(node: _TreeNode | None) -> str:
    """Extract text from a tree-sitter node; None-safe ("" for None text/node)."""
    if node is None:
        return ""
    text: bytes | str | None = node.text
    if text is None:
        return ""
    return text.decode("utf-8", errors="replace") if isinstance(text, bytes) else str(text)


# ----------------------------------------------------------
# Anti-pattern merge (rule_loader / validators.pipeline, Phase 34)
# ----------------------------------------------------------


def merge_anti_patterns(
    base_patterns: list[dict[str, Any]], custom_patterns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge custom anti-patterns over base ones by ID.

    Custom patterns with an ID matching a base pattern override it
    (via `severity_override` when present, else full replacement);
    new IDs are appended. Returns a new list — the returned list never
    aliases base_patterns (ADR-034 copy semantics).
    """
    if not custom_patterns:
        return list(base_patterns)

    base_ids = {p["id"] for p in base_patterns}
    merged: list[dict[str, Any]] = []
    for p in base_patterns:
        match = next((cp for cp in custom_patterns if cp["id"] == p["id"]), None)
        if match is None:
            merged.append(p)
        elif "severity_override" in match:
            overridden = dict(p)
            overridden["severity"] = match["severity_override"]
            merged.append(overridden)
        else:
            merged.append(match)
    merged.extend(cp for cp in custom_patterns if cp["id"] not in base_ids)
    return merged


def superseded_rule_ids(patterns: list[dict[str, Any]]) -> set[str]:
    """Collect rule IDs declared as superseded by the given patterns."""
    superseded: set[str] = set()
    for pattern in patterns:
        value = pattern.get("supersedes", [])
        if isinstance(value, str):
            superseded.add(value)
        else:
            superseded.update(item for item in value if isinstance(item, str))
    return superseded


# ----------------------------------------------------------
# Cache helpers (rule_loader / validators.cli, Phase 34)
# ----------------------------------------------------------


def load_cache(cache_file: Path) -> dict[str, str]:
    """Load a JSON dict cache from disk; empty dict on missing/corrupt file."""
    if not cache_file.exists():
        return {}
    try:
        result: dict[str, str] = json.loads(cache_file.read_text())
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache_file: Path, cache: dict[str, str]) -> None:
    """Persist a JSON dict cache to disk."""
    try:
        cache_file.write_text(json.dumps(cache))
    except OSError:
        pass


# ----------------------------------------------------------
# Severity counting mixin (rules / rules_engine models, Phase 34)
# ----------------------------------------------------------


class SeverityCountsMixin:
    """Provides error_count / warning_count / info_count from an issues list."""

    issues: list[Any]

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")


# ----------------------------------------------------------
# 治理层文档清单 (唯一真源)
# ----------------------------------------------------------


GOVERNANCE_DOCS: list[str] = [
    "docs/efficiency/ai-code-generation-quality.md",
    "docs/efficiency/ai-model-selection.md",
    "docs/efficiency/ai-sdlc.md",
    "docs/efficiency/ai-code-review-checklist.md",
    "docs/efficiency/ai-nondeterministic-testing.md",
    "docs/efficiency/ai-hallucination-mitigation.md",
    "docs/efficiency/ai-code-licensing.md",
    "docs/efficiency/ai-dev-environment.md",
    "docs/efficiency/ai-context-window-management.md",
    "docs/efficiency/ai-performance-benchmarks.md",
    "docs/efficiency/ai-debugging-standards.md",
    "docs/efficiency/ai-version-control.md",
    "docs/efficiency/ai-deployment-operations.md",
    "docs/efficiency/ai-developer-training.md",
    "docs/efficiency/ai-dev-toolchain.md",
]
