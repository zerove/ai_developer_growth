#!/usr/bin/env python3
"""
Enhanced Language & Framework Detector

Detects the primary programming language and framework of a project directory
by analyzing file extensions, config files, and directory structure.

Usage:
    python detect_language.py <project_dir>
    python detect_language.py . --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Extension to language mapping
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".zig": "zig",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".scala": "scala",
    ".clj": "clojure",
    ".ex": "elixir",
    ".exs": "elixir",
    ".hs": "haskell",
}


def detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from a file's extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


# Config file to (language, framework) mapping
CONFIG_MARKERS: dict[str, tuple[str, str | None]] = {
    "pyproject.toml": ("python", None),
    "setup.py": ("python", None),
    "setup.cfg": ("python", None),
    "Pipfile": ("python", None),
    "requirements.txt": ("python", None),
    "poetry.lock": ("python", None),
    "Cargo.toml": ("rust", None),
    "go.mod": ("go", None),
    "go.sum": ("go", None),
    "package.json": ("javascript", None),
    "tsconfig.json": ("typescript", None),
    "pom.xml": ("java", None),
    "build.gradle": ("java", None),
    "build.gradle.kts": ("kotlin", None),
    "Gemfile": ("ruby", None),
    "composer.json": ("php", None),
    "Cargo.lock": ("rust", None),
    "CMakeLists.txt": ("cpp", None),
    "Makefile": ("makefile", None),
    "build.sbt": ("scala", None),
}

# Framework detection from config file contents
FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    "react": ["react", "react-dom"],
    "nextjs": ["next", "nextjs"],
    "vue": ["vue", "nuxt", "nuxtjs"],
    "angular": ["@angular/core"],
    "svelte": ["svelte"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "tornado": ["tornado"],
    "express": ["express"],
    "nestjs": ["@nestjs/core"],
    "gin": ['"github.com/gin-gonic/gin"'],
    "echo": ['"github.com/labstack/echo"'],
    "fiber": ['"github.com/gofiber/fiber"'],
    "actix": ["actix-web"],
    "axum": ["axum"],
    "tokio": ["tokio"],
    "spring-boot": ["spring-boot"],
}

# Directories that indicate a language ecosystem
DIR_MARKERS: dict[str, str | None] = {
    "node_modules": "javascript",
    "vendor": None,
    "target": "rust",
    "__pycache__": "python",
    ".venv": "python",
    "venv": "python",
    "dist": None,
    "build": None,
    "src": None,
}

# Skip patterns
SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "target", "vendor",
    "__pycache__", ".venv", "venv", "dist", "build", ".tox",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "coverage",
    ".next", ".nuxt", ".output", "__snapshots__",
}


def count_extensions(dirpath: Path, max_files: int = 5000) -> Counter[str]:
    """Count file extensions in a directory (with depth limit)."""
    counter: Counter[str] = Counter()
    count = 0

    for filepath in dirpath.rglob("*"):
        if count >= max_files:
            break
        if not filepath.is_file():
            continue
        if any(part in SKIP_DIRS for part in filepath.parts):
            continue

        suffix = filepath.suffix.lower()
        if suffix in EXTENSION_MAP:
            counter[EXTENSION_MAP[suffix]] += 1
            count += 1

    return counter


def detect_framework_from_package_json(dirpath: Path) -> str | None:
    """Detect framework from package.json dependencies."""
    pkg_path = dirpath / "package.json"
    if not pkg_path.exists():
        return None

    try:
        import json as _json
        pkg = _json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return None

    all_deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        if key in pkg and isinstance(pkg[key], dict):
            all_deps.update(pkg[key])

    for framework, signatures in FRAMEWORK_SIGNATURES.items():
        if any(sig in all_deps for sig in signatures):
            return framework

    return None


def detect_framework_from_requirements(dirpath: Path) -> str | None:
    """Detect framework from Python requirements."""
    for req_file in ("requirements.txt", "pyproject.toml"):
        req_path = dirpath / req_file
        if not req_path.exists():
            continue

        try:
            content = req_path.read_text(encoding="utf-8")
        except OSError:
            continue

        for framework, signatures in FRAMEWORK_SIGNATURES.items():
            if any(sig in content for sig in signatures):
                return framework

    return None


def detect_framework_from_go_mod(dirpath: Path) -> str | None:
    """Detect framework from go.mod."""
    go_mod = dirpath / "go.mod"
    if not go_mod.exists():
        return None

    try:
        content = go_mod.read_text(encoding="utf-8")
    except OSError:
        return None

    for framework, signatures in FRAMEWORK_SIGNATURES.items():
        if any(sig in content for sig in signatures):
            return framework

    return None


def detect_framework(dirpath: Path, language: str) -> str | None:
    """Detect framework based on language."""
    if language == "typescript" or language == "javascript":
        return detect_framework_from_package_json(dirpath)
    elif language == "python":
        return detect_framework_from_requirements(dirpath)
    elif language == "go":
        return detect_framework_from_go_mod(dirpath)
    return None


def detect_language(dirpath: Path) -> dict[str, object]:
    """Detect the primary language and framework of a project."""
    result: dict[str, object] = {
        "language": "unknown",
        "framework": None,
        "confidence": 0.0,
        "file_counts": {},
    }

    # 1. Check config markers first (highest confidence)
    for config_file, lang_info in CONFIG_MARKERS.items():
        if (dirpath / config_file).exists():
            if lang_info is not None:
                lang, framework = lang_info
                # Special handling for package.json (might be TS)
                if config_file == "package.json":
                    tsconfig_exists = (dirpath / "tsconfig.json").exists()
                    lang = "typescript" if tsconfig_exists else "javascript"
                result["language"] = lang
                result["confidence"] = 0.9
                result["framework"] = detect_framework(dirpath, lang)
                return result

    # 2. Fall back to file extension counting
    counts = count_extensions(dirpath)
    if not counts:
        return result

    result["file_counts"] = dict(counts.most_common(10))

    total = sum(counts.values())
    if total == 0:
        return result

    primary, primary_count = counts.most_common(1)[0]
    confidence = primary_count / total

    result["language"] = primary
    result["confidence"] = round(confidence, 2)
    result["framework"] = detect_framework(dirpath, primary)

    return result


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Detect project language and framework")
    parser.add_argument("path", type=Path, nargs="?", default=Path("."),
                        help="Project directory (default: current)")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output as JSON")

    args = parser.parse_args()

    if not args.path.is_dir():
        print(f"Error: Not a directory: {args.path}", file=sys.stderr)
        return 1

    result = detect_language(args.path)

    if args.json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Language:  {result['language']}")
        print(f"Framework: {result['framework'] or 'N/A'}")
        print(f"Confidence: {result['confidence']}")
        if result["file_counts"]:
            print("File counts:")
            for lang, count in result["file_counts"].items():  # type: ignore
                print(f"  {lang}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
