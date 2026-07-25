"""Constants for the ADG Governance rules engine.

Centralized configuration constants to avoid magic numbers and strings.
"""

from __future__ import annotations

# File extensions for code detection
CODE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".kt": "kotlin",
    ".swift": "swift",
    ".scala": "scala",
    ".dart": "dart",
    ".r": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".hs": "haskell",
    ".ex": "elixir",
    ".zig": "zig",
}

# File extensions for incremental checks (subset of CODE_EXTENSIONS)
INCREMENTAL_EXTENSIONS: set[str] = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".java", ".go", ".cs"}

# Directories to ignore during scanning
IGNORE_DIRS: set[str] = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    "site",
    ".tox",
    ".eggs",
    "*.egg-info",
}

# Severity levels
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Default thresholds
DEFAULT_THRESHOLDS: dict[str, int] = {
    "max_function_length": 50,
    "max_file_length": 500,
    "max_line_length": 120,
    "max_nesting_depth": 4,
    "max_function_params": 7,
    "max_cyclomatic_complexity": 10,
}

# Timeouts
GIT_TIMEOUT_SECONDS = 30
LINTER_TIMEOUT_SECONDS = 30
