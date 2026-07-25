"""Language and framework detection for ADG CLI."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.core import (
    _ADG_HOME, _ADG_SOURCE, _get_rules_path,
    SKIP_DIRS, MAX_FILES,
)

# ── Language Detection Constants ──

EXTENSION_MAP: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".rs": "rust", ".go": "go", ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin", ".cs": "csharp",
    ".php": "php", ".rb": "ruby",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".h": "cpp",
    ".swift": "swift", ".dart": "dart", ".scala": "scala",
    ".clj": "clojure", ".ex": "elixir", ".exs": "elixir",
    ".hs": "haskell", ".zig": "zig", ".lua": "lua",
    ".r": "r", ".R": "r", ".ps1": "powershell",
    ".pl": "perl", ".pm": "perl",
    ".asm": "assembly", ".s": "assembly", ".S": "assembly",
    ".f90": "fortran", ".f": "fortran",
    ".graphql": "graphql", ".gql": "graphql",
}

CONFIG_MARKERS: dict[str, str | None] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "package.json": None,  # could be JS or TS
    "tsconfig.json": "typescript",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "Gemfile": "ruby",
    "composer.json": "php",
    "CMakeLists.txt": "cpp",
    "build.sbt": "scala",
}

FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    # JavaScript/TypeScript frameworks (order matters for detection)
    "nextjs": ["next", "nextjs"],
    "react": ["react", "react-dom"],
    "vue": ["vue", "nuxt"],
    "angular": ["@angular/core"],
    "express": ["express"],
    "nestjs": ["@nestjs/core"],
    # Python frameworks
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    # Go frameworks
    "gin": ["github.com/gin-gonic/gin"],
    # Rust frameworks
    "actix": ["actix-web"],
    "axum": ["axum"],
    # Java frameworks
    "spring-boot": ["spring-boot"],
    "spring": ["spring"],
}


def detect_language(dirpath: Path) -> dict[str, Any]:
    """Detect primary language and framework of a project."""
    result: dict[str, Any] = {"language": "unknown", "framework": None, "confidence": 0.0}

    # 1. Check config files
    for config_file, lang in CONFIG_MARKERS.items():
        if (dirpath / config_file).exists():
            if config_file == "package.json":
                lang = "typescript" if (dirpath / "tsconfig.json").exists() else "javascript"
            result["language"] = lang or "unknown"
            result["confidence"] = 0.9
            result["framework"] = _detect_framework(dirpath, lang)
            return result

    # 2. Count file extensions
    counter: Counter[str] = Counter()
    count = 0
    for filepath in dirpath.rglob("*"):
        if count >= MAX_FILES:
            break
        if not filepath.is_file():
            continue
        if any(part in SKIP_DIRS for part in filepath.parts):
            continue
        suffix = filepath.suffix.lower()
        if suffix in EXTENSION_MAP:
            counter[EXTENSION_MAP[suffix]] += 1
            count += 1

    if not counter:
        return result

    total = sum(counter.values())
    primary, primary_count = counter.most_common(1)[0]
    result["language"] = primary
    result["confidence"] = round(primary_count / total, 2)
    result["framework"] = _detect_framework(dirpath, primary)
    return result


def _detect_framework(dirpath: Path, language: str | None) -> str | None:
    """Detect framework from project config files."""
    # Check package.json
    pkg_path = dirpath / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            all_deps: dict[str, str] = {}
            for key in ("dependencies", "devDependencies"):
                if key in pkg and isinstance(pkg[key], dict):
                    all_deps.update(pkg[key])
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig in all_deps for sig in signatures):
                    return framework
        except (OSError, json.JSONDecodeError):
            pass

    # Check Python requirements
    for req_file in ("requirements.txt", "pyproject.toml"):
        req_path = dirpath / req_file
        if req_path.exists():
            try:
                content = req_path.read_text(encoding="utf-8").lower()
                for framework, signatures in FRAMEWORK_SIGNATURES.items():
                    if any(sig.lower() in content for sig in signatures):
                        return framework
            except OSError:
                pass

    # Check for manage.py (Django indicator)
    if (dirpath / "manage.py").exists():
        try:
            content = (dirpath / "manage.py").read_text(encoding="utf-8")
            if "django" in content.lower():
                return "django"
        except OSError:
            pass

    # Check for settings.py in common Django locations
    for settings_path in ["settings.py", "config/settings.py", "myproject/settings.py"]:
        if (dirpath / settings_path).exists():
            return "django"

    # Check go.mod
    go_mod = dirpath / "go.mod"
    if go_mod.exists():
        try:
            content = go_mod.read_text(encoding="utf-8")
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig in content for sig in signatures):
                    return framework
        except OSError:
            pass

    # Check Java build files (pom.xml, build.gradle)
    for build_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
        build_path = dirpath / build_file
        if build_path.exists():
            try:
                content = build_path.read_text(encoding="utf-8")
                if "spring" in content.lower():
                    return "spring"
            except OSError:
                pass

    # Check Rust Cargo.toml
    cargo_toml = dirpath / "Cargo.toml"
    if cargo_toml.exists():
        try:
            content = cargo_toml.read_text(encoding="utf-8").lower()
            for framework, signatures in FRAMEWORK_SIGNATURES.items():
                if any(sig.lower() in content for sig in signatures):
                    return framework
        except OSError:
            pass

    return None


def _detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from a single file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file. Tries PyYAML first, falls back to simple parser."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        return _simple_yaml_parse(path)
    except Exception:
        return {}


def _simple_yaml_parse(path: Path) -> dict[str, Any]:
    """Minimal YAML parser for anti_patterns.yml and config files (no PyYAML needed)."""
    content = path.read_text(encoding="utf-8")
    result: dict[str, Any] = {"anti_patterns": []}
    current_rule: dict[str, Any] | None = None
    current_section: str | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Anti-pattern list item (check BEFORE top-level keys)
        if stripped.startswith("- id:"):
            if current_rule:
                result["anti_patterns"].append(current_rule)
            current_rule = {"id": stripped.split(":", 1)[1].strip()}
            current_section = None
            continue

        # Top-level keys (only lines NOT starting with space and NOT starting with -)
        if not line.startswith(" ") and not line.startswith("-") and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")

            if key == "language":
                result["language"] = val
            elif key == "version":
                result["version"] = val
            elif key == "skip_patterns":
                current_section = "skip_patterns"
                result["skip_patterns"] = []
            elif key == "severity_overrides":
                current_section = "severity_overrides"
                result["severity_overrides"] = {}
            elif key == "framework_hints":
                current_section = "framework_hints"
                result["framework_hints"] = {}
            elif key == "anti_patterns":
                current_section = "anti_patterns"
            continue

        # Handle skip_patterns list items
        if current_section == "skip_patterns" and stripped.startswith("- "):
            pattern = stripped[2:].strip().strip("'\"")
            if pattern:
                result["skip_patterns"].append(pattern)
            continue

        # Handle severity_overrides key: value pairs
        if current_section == "severity_overrides" and ":" in stripped and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and val:
                result["severity_overrides"][key] = val
            continue

        # Handle framework_hints key: value pairs
        if current_section == "framework_hints" and ":" in stripped and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and val:
                result["framework_hints"][key] = val
            continue

        # Rule fields
        if current_rule and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key in ("name", "severity", "category", "pattern", "message", "fix_hint", "fix_replacement"):
                current_rule[key] = val
            elif key == "ignore_case" and val == "true":
                current_rule["ignore_case"] = True
            elif key == "multiline" and val == "true":
                current_rule["multiline"] = True

    if current_rule:
        result["anti_patterns"].append(current_rule)

    return result
