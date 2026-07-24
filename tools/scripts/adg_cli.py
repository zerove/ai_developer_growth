#!/usr/bin/env python3
"""
ADG - AI Developer Governance CLI

Checks code against language-specific anti-pattern rules, security patterns,
and quality standards. Self-contained - no external dependencies beyond PyYAML.

Usage:
    adg check <path>                    # auto-detect language, check all
    adg check <path> --lang python      # force language
    adg check <path> --severity error   # only errors
    adg detect <path>                   # detect project language
    adg list-rules --lang <lang>        # list rules for language
    adg install-hooks [path]            # install pre-commit hook
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

_ADG_HOME = Path(os.environ.get("ADG_HOME", Path.home() / ".config" / "adg"))
_RULES_PATH = _ADG_HOME / "rules"

# Fallback: check if ai_developer_growth source is available
_ADG_SOURCE = Path.home() / "dev" / "ai_developer_growth" / "ai-dev-framework"


def _get_rules_path() -> Path:
    """Get the rules directory, preferring config, falling back to source."""
    if _RULES_PATH.exists() and (_RULES_PATH / "languages").exists():
        return _RULES_PATH
    if _ADG_SOURCE.exists():
        return _ADG_SOURCE
    print(f"Error: Rules not found at {_RULES_PATH} or {_ADG_SOURCE}", file=sys.stderr)
    sys.exit(1)


def load_project_config(dirpath: Path | None = None) -> dict[str, Any]:
    """Load project-level ADG configuration.

    Looks for:
    1. .adg/rules.yml in project root
    2. ~/.config/adg/rules.yml as global config

    Returns merged configuration with project overriding global.
    """
    config = {
        "custom_rules": [],
        "skip_patterns": [],
        "severity_overrides": {},
        "framework_hints": {},
    }

    # Load global config first
    global_config_path = Path.home() / ".config" / "adg" / "rules.yml"
    if global_config_path.exists():
        try:
            global_config = _simple_yaml_parse(global_config_path)
            config = _merge_config(config, global_config)
        except Exception:
            pass

    # Load project config (overrides global)
    if dirpath:
        project_config_path = dirpath / ".adg" / "rules.yml"
        if project_config_path.exists():
            try:
                project_config = _simple_yaml_parse(project_config_path)
                # Map anti_patterns to custom_rules if present
                if "anti_patterns" in project_config:
                    project_config["custom_rules"] = project_config.pop("anti_patterns")
                config = _merge_config(config, project_config)
            except Exception:
                pass

    return config


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two configuration dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result:
            if isinstance(result[key], list) and isinstance(value, list):
                result[key] = result[key] + value
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key].update(value)
            else:
                result[key] = value
        else:
            result[key] = value

    return result


# ──────────────────────────────────────────────────────────
# Language Detection
# ──────────────────────────────────────────────────────────

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
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
    ".swift": "swift",
    ".dart": "dart",
    ".scala": "scala",
    ".clj": "clojure",
    ".ex": "elixir",
    ".exs": "elixir",
    ".hs": "haskell",
    ".zig": "zig",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".ps1": "powershell",
    ".pl": "perl",
    ".pm": "perl",
    ".asm": "assembly",
    ".s": "assembly",
    ".S": "assembly",
    ".f90": "fortran",
    ".f": "fortran",
    ".graphql": "graphql",
    ".gql": "graphql",
}

CONFIG_MARKERS: dict[tuple[str, str | None]] = {
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

SKIP_DIRS = {
    ".git",
    ".svn",
    "node_modules",
    "target",
    "vendor",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "coverage",
    ".next",
    ".nuxt",
    # Generated documentation / build output
    "book",
    "site",
    "_build",
    "out",
    "public",
    "static",
    # IDE / editor
    ".idea",
    ".vscode",
    ".vs",
    "*.swp",
    # Cache directories
    ".cache",
    "tmp",
    ".tmp",
}

MAX_FILES = 5000

# Skip generated/minified files
SKIP_EXTENSIONS = {
    ".min.js",
    ".min.css",
    ".map",
    ".lock",
    ".sum",
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".dat",
    ".db",
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


# ──────────────────────────────────────────────────────────
# Rule Loading
# ──────────────────────────────────────────────────────────


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
    current_section: str | None = None  # For skip_patterns, severity_overrides, etc.

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


def load_rules_for_language(language: str) -> dict[str, Any]:
    """Load anti-pattern rules for a specific language."""
    rules_path = _get_rules_path()
    lang_rules_file = rules_path / "languages" / language / "rules.d" / "anti_patterns.yml"

    lang_rules: dict[str, Any] = {"anti_patterns": []}
    if lang_rules_file.exists():
        lang_rules = _load_yaml(lang_rules_file)

    # Load cross-language security rules
    security_file = rules_path / "common" / "security.yml"
    security_rules: dict[str, Any] = {"anti_patterns": []}
    if security_file.exists():
        security_rules = _load_yaml(security_file)

    # Merge: language-specific + security
    all_patterns = lang_rules.get("anti_patterns", []) + security_rules.get("anti_patterns", [])
    return {"anti_patterns": all_patterns, "language": language}


def load_framework_rules(framework: str) -> dict[str, Any]:
    """Load anti-pattern rules for a specific framework."""
    rules_path = _get_rules_path()
    fw_rules_file = rules_path / "frameworks" / framework / "rules.d" / "anti_patterns.yml"

    if fw_rules_file.exists():
        return _load_yaml(fw_rules_file)
    return {"anti_patterns": []}


# ──────────────────────────────────────────────────────────
# Code Checking
# ──────────────────────────────────────────────────────────


@dataclass
class Issue:
    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    column: int
    message: str
    fix_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }


def check_file(filepath: Path, rules: dict[str, Any], severity_filter: str | None = None) -> list[Issue]:
    """Check a single file against rules."""
    issues: list[Issue] = []

    if not filepath.exists() or filepath.stat().st_size == 0:
        return issues

    # Skip generated/minified files
    if filepath.suffix in SKIP_EXTENSIONS or filepath.name.endswith(".min.js"):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return issues

    lines = content.split("\n")

    for pattern_def in rules.get("anti_patterns", []):
        severity = pattern_def.get("severity", "warning")
        if severity_filter and _severity_rank(severity) > _severity_rank(severity_filter):
            continue

        issues.extend(_check_pattern(filepath, content, lines, pattern_def))

    return issues


# ──────────────────────────────────────────────────────────
# Auto-fix Support
# ──────────────────────────────────────────────────────────

# Fix rules: pattern_id -> (regex_pattern, replacement)
FIX_RULES: dict[str, dict[str, Any]] = {
    # Python fixes
    "py-bare-except": {
        "pattern": r"except\s*:",
        "replacement": "except Exception:",
        "language": "python",
    },
    "py-print-statement": {
        "pattern": r"\bprint\(",
        "replacement": None,  # Requires context-aware replacement
        "language": "python",
    },
    # JavaScript/TypeScript fixes
    "js-==null": {
        "pattern": r"==\s*null",
        "replacement": "=== null",
        "language": "javascript",
    },
    "js-==undefined": {
        "pattern": r"==\s*undefined",
        "replacement": "=== undefined",
        "language": "javascript",
    },
    "js-!=null": {
        "pattern": r"!=\s*null",
        "replacement": "!== null",
        "language": "javascript",
    },
    "js-!=undefined": {
        "pattern": r"!=\s*undefined",
        "replacement": "!== undefined",
        "language": "javascript",
    },
    "js-eval": {
        "pattern": r"\beval\(",
        "replacement": None,  # Requires manual fix
        "language": "javascript",
    },
    # Rust fixes
    "rust-unwrap": {
        "pattern": r"\.unwrap\(\)",
        "replacement": None,  # Requires context
        "language": "rust",
    },
    # Common fixes
    "common-eval-exec": {
        "pattern": r"\b(eval|exec)\(",
        "replacement": None,  # Requires manual fix
        "language": "common",
    },
    "common-hardcoded-secret": {
        "pattern": r'(SECRET|PASSWORD|API_KEY|TOKEN)\s*=\s*["\'][^"\']+["\']',
        "replacement": None,  # Requires env var
        "language": "common",
    },
    # Go fixes
    "go-println": {
        "pattern": r"\bfmt\.Println\(",
        "replacement": "log.Println(",
        "language": "go",
    },
    "go-err-nil": {
        "pattern": r"if err != nil \{\s*return err\s*\}",
        "replacement": None,  # Requires context
        "language": "go",
    },
    # TypeScript fixes
    "ts-any": {
        "pattern": r":\s*any\b",
        "replacement": None,  # Requires context
        "language": "typescript",
    },
    "ts-ignore": {
        "pattern": r"//\s*@ts-ignore",
        "replacement": None,  # Requires context
        "language": "typescript",
    },
    # Rust extended
    "rust-unwrap-question": {
        "pattern": r"\.unwrap\(\)",
        "replacement": ".unwrap_or_default()",
        "language": "rust",
    },
    "rust-panic-macro": {
        "pattern": r"\bpanic!\(",
        "replacement": "return Err(",
        "language": "rust",
    },
    # Python extended
    "py-global": {
        "pattern": r"\bglobal\s+\w+",
        "replacement": None,  # Requires refactoring
        "language": "python",
    },
    "py-mutable-default": {
        "pattern": r"def\s+\w+\(.*?=\s*(\[\]|\{\})\)",
        "replacement": None,  # Requires None default
        "language": "python",
    },
}


# ──────────────────────────────────────────────────────────
# Incremental Check (git diff integration)
# ──────────────────────────────────────────────────────────


def _get_git_changed_files(since: str, cwd: Path | None = None) -> list[Path]:
    """Get list of files changed since a git reference.

    Args:
        since: Git reference (HEAD~1, commit hash, branch, etc.)
        cwd: Working directory (defaults to current)

    Returns:
        List of changed file paths
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACM", since],
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=10,
        )
        if result.returncode != 0:
            print(f"Warning: git diff failed: {result.stderr}", file=sys.stderr)
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                fp = Path(line.strip())
                if fp.is_file():
                    files.append(fp)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: git command failed: {e}", file=sys.stderr)
        return []


def _get_unstaged_files(cwd: Path | None = None) -> list[Path]:
    """Get list of unstaged changed files."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=10,
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                fp = Path(line.strip())
                if fp.is_file():
                    files.append(fp)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_staged_files(cwd: Path | None = None) -> list[Path]:
    """Get list of staged files."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=10,
        )
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                fp = Path(line.strip())
                if fp.is_file():
                    files.append(fp)
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


# ──────────────────────────────────────────────────────────
# SARIF Output Format (GitHub Code Scanning)
# ──────────────────────────────────────────────────────────


def _format_sarif(issues: list[Issue], language: str, framework: str | None) -> str:
    """Format issues as SARIF 2.1.0 for GitHub Code Scanning."""
    rules = {}
    results = []

    for issue in issues:
        # Collect unique rules
        if issue.rule_id not in rules:
            rules[issue.rule_id] = {
                "id": issue.rule_id,
                "shortDescription": {"text": issue.message},
                "fullDescription": {"text": issue.message},
                "helpUri": f"https://github.com/ai-developer-growth/rules/{issue.rule_id}",
                "properties": {
                    "category": issue.category,
                    "language": language,
                },
            }

        # Map severity to SARIF level
        level_map = {"error": "error", "warning": "warning", "info": "note"}
        level = level_map.get(issue.severity, "warning")

        results.append(
            {
                "ruleId": issue.rule_id,
                "level": level,
                "message": {"text": issue.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": issue.file},
                            "region": {
                                "startLine": issue.line,
                                "startColumn": issue.column,
                            },
                        },
                    }
                ],
                "fixes": [
                    {
                        "description": {"text": issue.fix_hint},
                        "artifactChanges": [
                            {
                                "artifactLocation": {"uri": issue.file},
                                "replacements": [
                                    {
                                        "deletedRegion": {
                                            "startLine": issue.line,
                                            "startColumn": issue.column,
                                        },
                                        "insertedContent": {"text": issue.fix_hint},
                                    }
                                ],
                            }
                        ],
                    }
                ]
                if issue.fix_hint
                else [],
            }
        )

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "adg",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/ai-developer-growth/adg",
                        "rules": list(rules.values()),
                    },
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif, indent=2)


# ──────────────────────────────────────────────────────────
# Rule Authoring Tool
# ──────────────────────────────────────────────────────────

_RULE_TEMPLATE = """# {id}
# Language: {language}
# Category: {category}
# Severity: {severity}

- id: {id}
  severity: {severity}
  category: {category}
  pattern: "{pattern}"
  message: "{message}"
  fix_hint: "{fix_hint}"
"""


def _create_rule_interactive() -> dict[str, Any]:
    """Interactively create a new rule."""
    print("=== ADG Rule Creator ===\n")

    rule_id = input("Rule ID (e.g., py-custom-rule): ").strip()
    if not rule_id:
        return {}

    language = input("Language (python/javascript/rust/go/typescript): ").strip()
    if not language:
        return {}

    category = input("Category (security/code_quality/performance/maintainability): ").strip()
    if not category:
        category = "code_quality"

    severity = input("Severity (error/warning/info): ").strip()
    if not severity:
        severity = "warning"

    pattern = input("Regex pattern to match: ").strip()
    if not pattern:
        return {}

    message = input("Issue message: ").strip()
    fix_hint = input("Fix hint (optional): ").strip()

    return {
        "id": rule_id,
        "language": language,
        "category": category,
        "severity": severity,
        "pattern": pattern,
        "message": message,
        "fix_hint": fix_hint,
    }


def _validate_rule(rule: dict[str, Any]) -> list[str]:
    """Validate a rule definition. Returns list of errors."""
    errors = []

    required_fields = ["id", "severity", "category", "pattern", "message"]
    for field in required_fields:
        if not rule.get(field):
            errors.append(f"Missing required field: {field}")

    if rule.get("severity") not in ("error", "warning", "info"):
        errors.append(f"Invalid severity: {rule.get('severity')}")

    if rule.get("category") not in ("security", "code_quality", "performance", "maintainability"):
        errors.append(f"Invalid category: {rule.get('category')}")

    # Test regex pattern
    if rule.get("pattern"):
        try:
            re.compile(rule["pattern"])
        except re.error as e:
            errors.append(f"Invalid regex pattern: {e}")

    return errors


def _test_rule(rule: dict[str, Any], test_files: list[Path]) -> dict[str, Any]:
    """Test a rule against test files."""
    results = {
        "rule_id": rule.get("id", "unknown"),
        "files_tested": len(test_files),
        "matches": [],
        "errors": [],
    }

    try:
        pattern = re.compile(rule["pattern"])
    except re.error as e:
        results["errors"].append(f"Invalid pattern: {e}")
        return results

    for filepath in test_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    results["matches"].append(
                        {
                            "file": str(filepath),
                            "line": line_num,
                            "column": 1,
                            "match": line.strip()[:100],
                        }
                    )
        except (OSError, UnicodeDecodeError) as e:
            results["errors"].append(f"Error reading {filepath}: {e}")

    return results


# ──────────────────────────────────────────────────────────
# Webhook Notification (Slack/DingTalk)
# ──────────────────────────────────────────────────────────


def _send_slack_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to Slack."""
    import time
    import urllib.request

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    color = "#36a64f" if error_count == 0 else "#ff0000"

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"ADG Governance Report - {project}",
                "text": f"Language: {language}\nErrors: {error_count} | Warnings: {warning_count} | Info: {info_count}",
                "fields": [
                    {"title": "Status", "value": "✅ Passed" if error_count == 0 else "❌ Failed", "short": True},
                    {"title": "Total Issues", "value": str(len(issues)), "short": True},
                ],
                "footer": "ADG CLI",
                "ts": int(time.time()),
            }
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Warning: Slack notification failed: {e}", file=sys.stderr)
        return False


def _send_dingtalk_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to DingTalk."""
    import urllib.request

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    status = "✅ 通过" if error_count == 0 else "❌ 失败"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"ADG 治理报告 - {project}",
            "text": f"## ADG 治理报告\n\n"
            f"**项目**: {project}\n"
            f"**语言**: {language}\n"
            f"**状态**: {status}\n\n"
            f"---\n\n"
            f"**错误**: {error_count}\n"
            f"**警告**: {warning_count}\n"
            f"**信息**: {info_count}\n"
            f"**总计**: {len(issues)}\n",
        },
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Warning: DingTalk notification failed: {e}", file=sys.stderr)
        return False


# ──────────────────────────────────────────────────────────
# Quality Trend Dashboard
# ──────────────────────────────────────────────────────────

_TREND_DATA_FILE = ".adg/trend.json"


def _load_trend_data(project_dir: Path) -> list[dict[str, Any]]:
    """Load historical trend data."""
    trend_file = project_dir / _TREND_DATA_FILE
    if trend_file.exists():
        try:
            return json.loads(trend_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_trend_data(project_dir: Path, data: list[dict[str, Any]]) -> None:
    """Save trend data."""
    trend_file = project_dir / _TREND_DATA_FILE
    trend_file.parent.mkdir(parents=True, exist_ok=True)
    trend_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _record_trend(project_dir: Path, issues: list[Issue], language: str) -> dict[str, Any]:
    """Record current check results as a trend data point."""
    from datetime import datetime

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    data_point = {
        "timestamp": datetime.now().isoformat(),
        "language": language,
        "errors": error_count,
        "warnings": warning_count,
        "info": info_count,
        "total": len(issues),
        "files_checked": len(set(i.file for i in issues)),
    }

    trend_data = _load_trend_data(project_dir)
    trend_data.append(data_point)

    # Keep last 100 data points
    if len(trend_data) > 100:
        trend_data = trend_data[-100:]

    _save_trend_data(project_dir, trend_data)
    return data_point


def _format_trend_report(trend_data: list[dict[str, Any]], output_json: bool = False) -> str:
    """Format trend data as a report."""
    if not trend_data:
        return "No trend data available. Run 'adg check' first."

    if output_json:
        return json.dumps(trend_data, indent=2)

    lines = ["ADG Quality Trend Report", "=" * 40, ""]

    # Summary
    latest = trend_data[-1]
    earliest = trend_data[0]

    lines.append(f"Period: {earliest['timestamp'][:10]} to {latest['timestamp'][:10]}")
    lines.append(f"Data points: {len(trend_data)}")
    lines.append("")

    # Trend
    if len(trend_data) >= 2:
        error_trend = latest["errors"] - earliest["errors"]
        warning_trend = latest["warnings"] - earliest["warnings"]

        lines.append("Trend:")
        lines.append(
            f"  Errors:   {latest['errors']} ({'↑' if error_trend > 0 else '↓' if error_trend < 0 else '→'} {abs(error_trend)})"
        )
        lines.append(
            f"  Warnings: {latest['warnings']} ({'↑' if warning_trend > 0 else '↓' if warning_trend < 0 else '→'} {abs(warning_trend)})"
        )
        lines.append("")

    # Recent history
    lines.append("Recent History:")
    lines.append("-" * 40)
    for point in trend_data[-10:]:
        ts = point["timestamp"][:16].replace("T", " ")
        lines.append(f"  {ts}: E={point['errors']} W={point['warnings']} I={point['info']}")

    return "\n".join(lines)


def _apply_fix(content: str, rule_id: str, fix_info: dict[str, Any]) -> tuple[str, bool]:
    """Apply a single fix to content. Returns (new_content, was_modified)."""
    import re

    pattern = fix_info.get("pattern")
    replacement = fix_info.get("replacement")

    if not pattern or replacement is None:
        return content, False

    new_content, count = re.subn(pattern, replacement, content)
    return new_content, count > 0


def fix_file(filepath: Path, rule_ids: list[str] | None = None) -> dict[str, Any]:
    """Apply fixes to a file. Returns stats about fixes applied."""

    if not filepath.exists():
        return {"fixed": 0, "skipped": 0, "errors": 1}

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"fixed": 0, "skipped": 0, "errors": 1}

    original_content = content
    fixed_count = 0
    skipped_count = 0

    # Filter rules if specific rule_ids provided
    applicable_rules = FIX_RULES
    if rule_ids:
        applicable_rules = {k: v for k, v in FIX_RULES.items() if k in rule_ids}

    for rule_id, fix_info in applicable_rules.items():
        new_content, was_modified = _apply_fix(content, rule_id, fix_info)
        if was_modified:
            content = new_content
            fixed_count += 1
        else:
            skipped_count += 1

    # Write back if modified
    if content != original_content:
        try:
            filepath.write_text(content, encoding="utf-8")
        except OSError:
            return {"fixed": 0, "skipped": 0, "errors": 1}

    return {"fixed": fixed_count, "skipped": skipped_count, "errors": 0}


def fix_directory(dirpath: Path, language: str | None = None) -> dict[str, Any]:
    """Apply fixes to all code files in a directory."""
    total_stats = {"fixed": 0, "skipped": 0, "errors": 0, "files": 0}

    for filepath in dirpath.rglob("*"):
        if not filepath.is_file():
            continue
        if any(part in SKIP_DIRS for part in filepath.parts):
            continue
        if filepath.suffix in SKIP_EXTENSIONS:
            continue

        # Filter by language if specified
        if language:
            file_lang = _detect_language_from_file(filepath)
            if file_lang and file_lang != language:
                continue

        # Filter applicable rules by language
        applicable_rules = {}
        for rule_id, fix_info in FIX_RULES.items():
            if language is None or fix_info.get("language") in (language, "common"):
                applicable_rules[rule_id] = fix_info

        if applicable_rules:
            stats = fix_file(filepath, list(applicable_rules.keys()))
            total_stats["fixed"] += stats["fixed"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            if stats["fixed"] > 0:
                total_stats["files"] += 1

    return total_stats


def _severity_rank(severity: str) -> int:
    """Return numeric rank for severity comparison."""
    return {"error": 0, "warning": 1, "info": 2}.get(severity, 3)


def _check_pattern(filepath: Path, content: str, lines: list[str], pattern_def: dict[str, Any]) -> list[Issue]:
    """Check a single pattern against file content."""
    issues: list[Issue] = []
    pattern = pattern_def.get("pattern", "")
    if not pattern:
        return issues

    # Check exclude patterns
    for exclude in pattern_def.get("exclude_patterns", []):
        if re.search(exclude, content):
            return []

    flags = re.IGNORECASE if pattern_def.get("ignore_case", False) else 0
    is_multiline = ("\n" in pattern or "\\n" in pattern) or pattern_def.get("multiline", False)

    if is_multiline:
        try:
            for match in re.finditer(pattern, content, flags | re.MULTILINE):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(_make_issue(filepath, line_num, 0, pattern_def))
        except re.error:
            pass
    else:
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            try:
                for match in re.finditer(pattern, line, flags):
                    issues.append(_make_issue(filepath, line_num, match.start() + 1, pattern_def))
            except re.error:
                continue

    return issues


def _make_issue(filepath: Path, line: int, column: int, pattern_def: dict[str, Any]) -> Issue:
    """Create an Issue from a pattern definition."""
    return Issue(
        rule_id=pattern_def.get("id", "unknown"),
        severity=pattern_def.get("severity", "warning"),
        category=pattern_def.get("category", "anti-pattern"),
        file=str(filepath),
        line=line,
        column=column,
        message=pattern_def.get("message", "Anti-pattern detected"),
        fix_hint=pattern_def.get("fix_hint", ""),
    )


def check_directory(
    dirpath: Path, rules: dict[str, Any], severity_filter: str | None = None, jobs: int = 1
) -> list[Issue]:
    """Check all code files in a directory.

    Args:
        dirpath: Directory to check
        rules: Rules to apply
        severity_filter: Filter by severity level
        jobs: Number of parallel jobs (1 = sequential)
    """
    # Collect files first
    files_to_check: list[Path] = []
    for filepath in dirpath.rglob("*"):
        if not filepath.is_file():
            continue
        if any(part in SKIP_DIRS for part in filepath.parts):
            continue
        if filepath.suffix in SKIP_EXTENSIONS:
            continue
        lang = _detect_language_from_file(filepath)
        if lang:
            files_to_check.append(filepath)

    # Check files (parallel or sequential)
    if jobs > 1 and len(files_to_check) > 1:
        return _check_files_parallel(files_to_check, rules, severity_filter, jobs)
    else:
        all_issues: list[Issue] = []
        for filepath in files_to_check:
            all_issues.extend(check_file(filepath, rules, severity_filter))
        return all_issues


def _check_files_parallel(
    files: list[Path], rules: dict[str, Any], severity_filter: str | None, jobs: int
) -> list[Issue]:
    """Check files in parallel using ProcessPoolExecutor."""
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    if not files:
        return []

    all_issues: list[Issue] = []

    # Limit jobs to CPU count or file count
    max_workers = min(jobs, len(files), os.cpu_count() or 4)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all files for checking
        future_to_file = {executor.submit(check_file, filepath, rules, severity_filter): filepath for filepath in files}

        # Collect results as they complete
        for future in as_completed(future_to_file):
            try:
                issues = future.result()
                all_issues.extend(issues)
            except Exception as e:
                # Log error but continue processing
                filepath = future_to_file[future]
                print(f"Warning: Error checking {filepath}: {e}", file=sys.stderr)

    return all_issues


# ──────────────────────────────────────────────────────────
# Output Formatting
# ──────────────────────────────────────────────────────────

_SEVERITY_COLORS = {"error": "\033[91m", "warning": "\033[93m", "info": "\033[96m"}
_RESET = "\033[0m"


def _format_human(issues: list[Issue], language: str, framework: str | None, files_checked: int) -> str:
    """Format issues as human-readable output."""
    lines: list[str] = []

    fw_str = f" + {framework}" if framework else ""
    lines.append(f"Language: {language}{fw_str} (auto-detected)")
    lines.append(f"Rules loaded: {len(issues)} issues found")
    lines.append("")

    # Group by file
    by_file: dict[str, list[Issue]] = {}
    for issue in issues:
        by_file.setdefault(issue.file, []).append(issue)

    for filepath, file_issues in sorted(by_file.items()):
        for issue in sorted(file_issues, key=lambda i: i.line):
            color = _SEVERITY_COLORS.get(issue.severity, "")
            loc = f"{issue.file}:{issue.line}:{issue.column}"
            lines.append(f"{loc}  {color}{issue.severity:7s}{_RESET}  {issue.rule_id:30s}  {issue.message}")
            if issue.fix_hint:
                lines.append(f"{' ' * len(loc)}  {' ' * 7}  {' ' * 30}  → {issue.fix_hint}")

    # Summary
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    lines.append("")
    parts = []
    if error_count:
        parts.append(f"\033[91m{error_count} error{'s' if error_count != 1 else ''}\033[0m")
    if warning_count:
        parts.append(f"\033[93m{warning_count} warning{'s' if warning_count != 1 else ''}\033[0m")
    if info_count:
        parts.append(f"\033[96m{info_count} info\033[0m")

    if parts:
        lines.append(f"{'  '.join(parts)} in {files_checked} file{'s' if files_checked != 1 else ''}")
    else:
        lines.append(f"\033[92m✓ All checks passed\033[0m ({files_checked} files)")

    return "\n".join(lines)


def _format_json(issues: list[Issue], language: str, framework: str | None, files_checked: int) -> str:
    """Format issues as JSON output."""
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    return json.dumps(
        {
            "language": language,
            "framework": framework,
            "files_checked": files_checked,
            "issues": [i.to_dict() for i in issues],
            "summary": {"error": error_count, "warning": warning_count, "info": info_count},
        },
        indent=2,
        ensure_ascii=False,
    )


# ──────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────


def cmd_check(args: argparse.Namespace) -> int:
    """Check code against rules."""
    target = Path(args.path).resolve()

    # Load project configuration
    project_config = load_project_config(target if target.is_dir() else target.parent)

    # Handle incremental check modes
    files: list[Path] = []
    since = getattr(args, "since", None)
    staged = getattr(args, "staged", False)
    unstaged = getattr(args, "unstaged", False)

    if since:
        # Check only files changed since git ref
        files = _get_git_changed_files(since, cwd=target.parent)
        if not files:
            print("No changed files found.", file=sys.stderr)
            return 0
        detected = detect_language(target)
    elif staged:
        # Check only staged files
        files = _get_staged_files(cwd=target.parent)
        if not files:
            print("No staged files found.", file=sys.stderr)
            return 0
        detected = detect_language(target)
    elif unstaged:
        # Check only unstaged files
        files = _get_unstaged_files(cwd=target.parent)
        if not files:
            print("No unstaged changes found.", file=sys.stderr)
            return 0
        detected = detect_language(target)
    elif target.is_file():
        files = [target]
        detected = detect_language(target.parent)
    else:
        skip_patterns = project_config.get("skip_patterns", [])
        for fp in target.rglob("*"):
            if fp.is_file() and any(part not in SKIP_DIRS for part in fp.parts):
                if fp.suffix not in SKIP_EXTENSIONS:
                    # Check skip patterns
                    if any(_match_pattern(fp, pat) for pat in skip_patterns):
                        continue
                    if _detect_language_from_file(fp):
                        files.append(fp)
        detected = detect_language(target)

    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, "framework", None) or detected.get("framework")

    # Use framework hint from config if not detected
    if not framework:
        framework = project_config.get("framework_hints", {}).get(language)

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules
    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    # Add custom rules from project config
    custom_rules = project_config.get("custom_rules", [])
    if custom_rules:
        rules["anti_patterns"].extend(custom_rules)

    # Apply severity overrides
    severity_overrides = project_config.get("severity_overrides", {})
    for rule in rules["anti_patterns"]:
        if rule["id"] in severity_overrides:
            rule["severity"] = severity_overrides[rule["id"]]

    # Check files
    all_issues: list[Issue] = []
    jobs = getattr(args, "jobs", 1)

    if jobs > 1 and len(files) > 1:
        # Parallel checking
        all_issues = _check_files_parallel(files, rules, args.severity, jobs)
    else:
        # Sequential checking
        for fp in files:
            all_issues.extend(check_file(fp, rules, args.severity))

    # Output
    sarif = getattr(args, "sarif", False)
    if sarif:
        print(_format_sarif(all_issues, language, framework))
    elif args.json:
        print(_format_json(all_issues, language, framework, len(files)))
    else:
        print(_format_human(all_issues, language, framework, len(files)))

    # Record trend if requested
    if getattr(args, "trend", False):
        _record_trend(target if target.is_dir() else target.parent, all_issues, language)

    # Send notification if requested
    notify_url = getattr(args, "notify", None)
    if notify_url:
        project_name = getattr(args, "project", ".")
        if notify_url.startswith("slack://"):
            webhook_url = notify_url.replace("slack://", "https://hooks.slack.com/services/")
            _send_slack_notification(webhook_url, all_issues, language, project_name)
        elif notify_url.startswith("dingtalk://"):
            webhook_url = notify_url.replace("dingtalk://", "https://oapi.dingtalk.com/robot/send?access_token=")
            _send_dingtalk_notification(webhook_url, all_issues, language, project_name)

    # Exit code: non-zero if errors found
    has_errors = any(i.severity == "error" for i in all_issues)
    return 1 if has_errors else 0


def _match_pattern(filepath: Path, pattern: str) -> bool:
    """Check if filepath matches a glob pattern."""
    import fnmatch

    return fnmatch.fnmatch(str(filepath), pattern) or fnmatch.fnmatch(filepath.name, pattern)


def cmd_fix(args: argparse.Namespace) -> int:
    """Apply automatic fixes to code files."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    # Detect language
    detected = detect_language(target)
    language = args.lang or detected.get("language")

    if args.json:
        stats = fix_file(target) if target.is_file() else fix_directory(target, language)
        # Add files key for single file
        if target.is_file():
            stats["files"] = 1 if stats["fixed"] > 0 else 0
        print(json.dumps(stats, indent=2))
    else:
        print(f"\n\033[1m\033[36m{'=' * 60}\033[0m")
        print("\033[1m\033[36m  ADG Auto-fix\033[0m")
        print(f"\033[1m\033[36m{'=' * 60}\033[0m\n")

        print(f"\033[1mTarget:\033[0m {target}")
        if language:
            print(f"\033[1mLanguage:\033[0m {language}")
        print()

        if target.is_file():
            stats = fix_file(target)
            stats["files"] = 1 if stats["fixed"] > 0 else 0
        else:
            stats = fix_directory(target, language)

        print("\033[1mResults:\033[0m")
        print(f"  Files modified: {stats['files']}")
        print(f"  Rules applied:  {stats['fixed']}")
        print(f"  Rules skipped:  {stats['skipped']}")
        print(f"  Errors:         {stats['errors']}")
        print()

        if stats["fixed"] > 0:
            print("\033[32m\033[1m✅ Fixes applied successfully\033[0m")
        elif stats["errors"] > 0:
            print("\033[31m\033[1m❌ Some errors occurred\033[0m")
        else:
            print("\033[33m\033[1m⚠️  No automatic fixes available\033[0m")
            print("   Some issues require manual fixes.")

    return 0 if stats["errors"] == 0 else 1


# ──────────────────────────────────────────────────────────
# Rule Authoring Commands
# ──────────────────────────────────────────────────────────


def cmd_rule(args: argparse.Namespace) -> int:
    """Handle rule authoring commands."""
    rule_cmd = getattr(args, "rule_command", None)

    if rule_cmd == "create":
        return _cmd_rule_create(args)
    elif rule_cmd == "test":
        return _cmd_rule_test(args)
    elif rule_cmd == "validate":
        return _cmd_rule_validate(args)
    else:
        print("Usage: adg rule {create|test|validate}", file=sys.stderr)
        return 1


def _cmd_rule_create(args: argparse.Namespace) -> int:
    """Create a new rule interactively."""
    rule = _create_rule_interactive()

    if not rule:
        print("Rule creation cancelled.", file=sys.stderr)
        return 1

    # Validate
    errors = _validate_rule(rule)
    if errors:
        print("Rule validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Output
    output_path = getattr(args, "output", None)
    if output_path:
        yaml_content = _RULE_TEMPLATE.format(**rule)
        Path(output_path).write_text(yaml_content)
        print(f"Rule saved to: {output_path}")
    else:
        print("\nGenerated rule:")
        print(_RULE_TEMPLATE.format(**rule))

    return 0


def _cmd_rule_test(args: argparse.Namespace) -> int:
    """Test a rule against files."""
    rule_file = Path(args.rule_file)
    if not rule_file.exists():
        print(f"Error: Rule file not found: {rule_file}", file=sys.stderr)
        return 1

    # Load rule from YAML
    try:
        import yaml

        with open(rule_file) as f:
            rule_data = yaml.safe_load(f)
    except ImportError:
        # Fallback: try simple parsing
        content = rule_file.read_text()
        rule_data = {"pattern": "", "message": ""}
        for line in content.split("\n"):
            if "pattern:" in line:
                rule_data["pattern"] = line.split("pattern:")[1].strip().strip('"')
            elif "message:" in line:
                rule_data["message"] = line.split("message:")[1].strip().strip('"')

    if not rule_data.get("pattern"):
        print("Error: No pattern found in rule file", file=sys.stderr)
        return 1

    # Get test files
    target = Path(args.path)
    test_files = []
    if target.is_file():
        test_files = [target]
    else:
        for fp in target.rglob("*"):
            if fp.is_file() and fp.suffix in (".py", ".js", ".ts", ".go", ".rs", ".java"):
                test_files.append(fp)

    if not test_files:
        print("No test files found.", file=sys.stderr)
        return 1

    # Test the rule
    results = _test_rule(rule_data, test_files)

    # Output
    print(f"\nRule: {results['rule_id']}")
    print(f"Files tested: {results['files_tested']}")
    print(f"Matches found: {len(results['matches'])}")

    if results["matches"]:
        print("\nMatches:")
        for match in results["matches"][:20]:  # Limit to 20
            print(f"  {match['file']}:{match['line']}: {match['match']}")

    if results["errors"]:
        print("\nErrors:")
        for e in results["errors"]:
            print(f"  - {e}")

    return 0 if not results["errors"] else 1


def _cmd_rule_validate(args: argparse.Namespace) -> int:
    """Validate a rule file."""
    rule_file = Path(args.rule_file)
    if not rule_file.exists():
        print(f"Error: Rule file not found: {rule_file}", file=sys.stderr)
        return 1

    # Load rule
    try:
        import yaml

        with open(rule_file) as f:
            rule = yaml.safe_load(f)
    except ImportError:
        content = rule_file.read_text()
        rule = {}
        for line in content.split("\n"):
            if "pattern:" in line:
                rule["pattern"] = line.split("pattern:")[1].strip().strip('"')
            elif "message:" in line:
                rule["message"] = line.split("message:")[1].strip().strip('"')
            elif "severity:" in line:
                rule["severity"] = line.split("severity:")[1].strip()
            elif "category:" in line:
                rule["category"] = line.split("category:")[1].strip()
            elif "id:" in line and not line.strip().startswith("#"):
                rule["id"] = line.split("id:")[1].strip()

    # Validate
    errors = _validate_rule(rule)

    if errors:
        print(f"\n❌ Validation failed for: {rule_file}")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print(f"\n✅ Validation passed for: {rule_file}")
        return 0


# ──────────────────────────────────────────────────────────
# Trend Dashboard Command
# ──────────────────────────────────────────────────────────


def cmd_trend(args: argparse.Namespace) -> int:
    """Show quality trend dashboard."""
    project_dir = Path(args.path).resolve()

    if getattr(args, "clear", False):
        trend_file = project_dir / _TREND_DATA_FILE
        if trend_file.exists():
            trend_file.unlink()
            print("Trend history cleared.")
        else:
            print("No trend history to clear.")
        return 0

    trend_data = _load_trend_data(project_dir)

    if getattr(args, "json", False):
        print(_format_trend_report(trend_data, output_json=True))
    else:
        print(_format_trend_report(trend_data))

    return 0


# ──────────────────────────────────────────────────────────
# Notify Command
# ──────────────────────────────────────────────────────────


def cmd_notify(args: argparse.Namespace) -> int:
    """Send governance report via webhook."""
    target = Path(args.path).resolve()

    # Detect language
    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules and check
    rules = load_rules_for_language(language)
    all_issues: list[Issue] = []

    if target.is_file():
        all_issues = check_file(target, rules)
    else:
        for fp in target.rglob("*"):
            if fp.is_file() and fp.suffix not in SKIP_EXTENSIONS:
                if _detect_language_from_file(fp):
                    all_issues.extend(check_file(fp, rules))

    # Send notification
    webhook_url = args.webhook
    project_name = getattr(args, "project", ".")

    if webhook_url.startswith("slack://"):
        url = webhook_url.replace("slack://", "https://hooks.slack.com/services/")
        success = _send_slack_notification(url, all_issues, language, project_name)
    elif webhook_url.startswith("dingtalk://"):
        url = webhook_url.replace("dingtalk://", "https://oapi.dingtalk.com/robot/send?access_token=")
        success = _send_dingtalk_notification(url, all_issues, language, project_name)
    else:
        print("Error: Unknown webhook scheme. Use slack:// or dingtalk://", file=sys.stderr)
        return 1

    if success:
        print("✅ Notification sent successfully")
    else:
        print("", file=sys.stderr)
        return 1

    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    """Detect project language and framework."""
    target = Path(args.path).resolve()
    result = detect_language(target)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Language:  {result['language']}")
        print(f"Framework: {result.get('framework') or 'N/A'}")
        print(f"Confidence: {result['confidence']}")

    return 0


def cmd_list_rules(args: argparse.Namespace) -> int:
    """List rules for a specific language."""
    rules = load_rules_for_language(args.lang)
    patterns = rules.get("anti_patterns", [])

    if args.json:
        print(json.dumps(patterns, indent=2, ensure_ascii=False))
        return 0

    print(f"Rules for: {args.lang}")
    print(f"Total: {len(patterns)} anti-patterns\n")

    # Group by severity
    for severity in ("error", "warning", "info"):
        group = [p for p in patterns if p.get("severity") == severity]
        if group:
            color = _SEVERITY_COLORS.get(severity, "")
            print(f"{color}{'=' * 60}")
            print(f"  {severity.upper()} ({len(group)} rules)")
            print(f"{'=' * 60}{_RESET}")
            for p in group:
                print(f"  {p.get('id', 'unknown'):30s}  {p.get('name', '')}")
                if p.get("message"):
                    print(f"  {' ' * 30}  → {p['message']}")
            print()

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a quality gate report."""
    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, "framework", None) or detected.get("framework")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules
    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    # Collect all issues
    all_issues: list[Issue] = []
    files_checked = 0

    if target.is_file():
        all_issues = check_file(target, rules)
        files_checked = 1
    else:
        for fp in target.rglob("*"):
            if fp.is_file() and any(part not in SKIP_DIRS for part in fp.parts):
                if fp.suffix not in SKIP_EXTENSIONS:
                    if _detect_language_from_file(fp):
                        all_issues.extend(check_file(fp, rules))
                        files_checked += 1

    # Count by severity
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for issue in all_issues:
        if issue.severity in severity_counts:
            severity_counts[issue.severity] += 1

    # Count by category
    category_counts: dict[str, int] = {}
    for issue in all_issues:
        cat = issue.category or "unknown"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Count by file
    file_counts: dict[str, int] = {}
    for issue in all_issues:
        file_counts[issue.file] = file_counts.get(issue.file, 0) + 1

    # Top files by issue count
    top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Determine pass/fail
    error_threshold = getattr(args, "error_threshold", 0)
    warning_threshold = getattr(args, "warning_threshold", -1)  # -1 = no limit
    passed = severity_counts["error"] <= error_threshold
    if warning_threshold >= 0:
        passed = passed and severity_counts["warning"] <= warning_threshold

    # Output
    if getattr(args, "json", False):
        report = {
            "language": language,
            "framework": framework,
            "files_checked": files_checked,
            "total_issues": len(all_issues),
            "severity": severity_counts,
            "categories": category_counts,
            "top_files": [{"file": f, "issues": c} for f, c in top_files],
            "passed": passed,
        }
        print(json.dumps(report, indent=2))
    else:
        # Color
        green = "\033[0;32m"
        red = "\033[0;31m"
        yellow = "\033[0;33m"
        cyan = "\033[0;36m"
        bold = "\033[1m"
        nc = "\033[0m"

        print(f"\n{bold}{cyan}{'=' * 60}{nc}")
        print(f"{bold}{cyan}  ADG Quality Gate Report{nc}")
        print(f"{bold}{cyan}{'=' * 60}{nc}\n")

        print(f"{bold}Project:{nc} {target}")
        print(f"{bold}Language:{nc} {language}" + (f" + {framework}" if framework else ""))
        print(f"{bold}Files Checked:{nc} {files_checked}")
        print()

        print(f"{bold}Issues by Severity:{nc}")
        print(f"  {red}Errors:   {severity_counts['error']}{nc}")
        print(f"  {yellow}Warnings: {severity_counts['warning']}{nc}")
        print(f"  Info:     {severity_counts['info']}")
        print()

        if category_counts:
            print(f"{bold}Issues by Category:{nc}")
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {cat}: {count}")
            print()

        if top_files:
            print(f"{bold}Top Files by Issues:{nc}")
            for filepath, count in top_files:
                print(f"  {filepath}: {count}")
            print()

        if passed:
            print(f"{green}{bold}✅ PASSED{nc} - Quality gate met")
        else:
            print(f"{red}{bold}❌ FAILED{nc} - Quality gate not met")
            if severity_counts["error"] > error_threshold:
                print(f"  Errors ({severity_counts['error']}) exceed threshold ({error_threshold})")
            if warning_threshold >= 0 and severity_counts["warning"] > warning_threshold:
                print(f"  Warnings ({severity_counts['warning']}) exceed threshold ({warning_threshold})")

    return 0 if passed else 1


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


# ──────────────────────────────────────────────────────────
# Default pre-push hook
# ──────────────────────────────────────────────────────────

_DEFAULT_PRE_PUSH_HOOK = """#!/bin/bash
# ADG Governance Pre-push Hook
# Installed by: adg install-hooks --pre-push

set -euo pipefail

REMOTE="$1"
URL="$2"

echo "🔍 ADG Pre-push Governance Check..."

# Try system adg first
if command -v adg &> /dev/null; then
    adg check . --severity error
elif [ -x "$HOME/.local/bin/adg" ]; then
    $HOME/.local/bin/adg check . --severity error
else
    echo "⚠️  adg not found. Skipping."
    exit 0
fi

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Pre-push check failed. Fix errors before pushing."
    echo "   Run: adg check ."
    echo "   Report: adg report ."
    echo "   Skip: git push --no-verify"
    exit 1
fi

echo "✅ Pre-push check passed."
"""


# ──────────────────────────────────────────────────────────
# Default pre-commit hook
# ──────────────────────────────────────────────────────────

_DEFAULT_PRE_COMMIT_HOOK = """#!/bin/bash
# ADG Governance Pre-commit Hook
# Installed by: adg install-hooks

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

CODE_FILES=$(echo "$STAGED_FILES" | grep -E '\\.(py|rs|ts|js|go|java|kt|rb|php|swift|dart|scala)$' || true)

if [ -z "$CODE_FILES" ]; then
    exit 0
fi

echo "🔍 ADG Governance Check..."

# Try system adg first, then python module
if command -v adg &> /dev/null; then
    adg check $CODE_FILES --severity error
elif python3 -c "import adg" 2>/dev/null; then
    python3 -m adg check $CODE_FILES --severity error
else
    echo "⚠️  adg not found. Install: cp $(dirname "$0")/adg ~/.local/bin/adg"
    exit 0
fi

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Governance check failed. Fix errors before commit."
    echo "   Run: adg check $CODE_FILES"
    echo "   Skip: git commit --no-verify"
    exit 1
fi

echo "✅ Governance check passed."
"""


# ──────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="adg",
        description="ADG - AI Developer Governance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # check
    check_p = sub.add_parser("check", help="Check code against rules")
    check_p.add_argument("path", help="File or directory to check")
    check_p.add_argument("--lang", help="Force language (skip auto-detection)")
    check_p.add_argument("--framework", help="Force framework (skip auto-detection)")
    check_p.add_argument(
        "--severity", choices=["error", "warning", "info"], help="Only show issues at this severity or higher"
    )
    check_p.add_argument("--json", action="store_true", help="Output as JSON")
    check_p.add_argument("--sarif", action="store_true", help="Output as SARIF (GitHub Code Scanning)")
    check_p.add_argument("-j", "--jobs", type=int, default=1, help="Number of parallel jobs (default: 1)")
    check_p.add_argument(
        "--since", type=str, default=None, help="Only check files changed since git ref (e.g., HEAD~1, main)"
    )
    check_p.add_argument("--staged", action="store_true", help="Only check staged files (for pre-commit)")
    check_p.add_argument("--unstaged", action="store_true", help="Only check unstaged changed files")
    check_p.add_argument("--trend", action="store_true", help="Record results for trend tracking")
    check_p.add_argument(
        "--notify", type=str, default=None, help="Send results to webhook (slack://... or dingtalk://...)"
    )
    check_p.add_argument("--project", type=str, default=".", help="Project name for notifications")

    # detect
    detect_p = sub.add_parser("detect", help="Detect project language/framework")
    detect_p.add_argument("path", nargs="?", default=".", help="Project directory")
    detect_p.add_argument("--json", action="store_true", help="Output as JSON")

    # list-rules
    list_p = sub.add_parser("list-rules", help="List rules for a language")
    list_p.add_argument("--lang", required=True, help="Language name")
    list_p.add_argument("--json", action="store_true", help="Output as JSON")

    # install-hooks
    install_p = sub.add_parser("install-hooks", help="Install pre-commit/pre-push hook")
    install_p.add_argument("path", nargs="?", default=".", help="Project directory")
    install_p.add_argument("--pre-push", action="store_true", help="Install pre-push hook instead of pre-commit")

    # report
    report_p = sub.add_parser("report", help="Generate quality gate report")
    report_p.add_argument("path", help="File or directory to report on")
    report_p.add_argument("--lang", help="Force language (skip auto-detection)")
    report_p.add_argument("--framework", help="Force framework (skip auto-detection)")
    report_p.add_argument("--error-threshold", type=int, default=0, help="Max errors allowed (default: 0)")
    report_p.add_argument("--warning-threshold", type=int, default=-1, help="Max warnings allowed (-1 = no limit)")
    report_p.add_argument("--json", action="store_true", help="Output as JSON")

    # fix
    fix_p = sub.add_parser("fix", help="Apply automatic fixes to code")
    fix_p.add_argument("path", help="File or directory to fix")
    fix_p.add_argument("--lang", help="Force language (skip auto-detection)")
    fix_p.add_argument("--json", action="store_true", help="Output as JSON")

    # rule (authoring tool)
    rule_p = sub.add_parser("rule", help="Create/test governance rules")
    rule_sub = rule_p.add_subparsers(dest="rule_command")
    rule_create = rule_sub.add_parser("create", help="Create a new rule interactively")
    rule_create.add_argument("--output", type=str, help="Output YAML file path")
    rule_test = rule_sub.add_parser("test", help="Test a rule against files")
    rule_test.add_argument("rule-file", type=str, help="Rule YAML file to test")
    rule_test.add_argument("path", type=str, help="Files/directory to test against")
    rule_validate = rule_sub.add_parser("validate", help="Validate a rule file")
    rule_validate.add_argument("rule-file", type=str, help="Rule YAML file to validate")

    # trend
    trend_p = sub.add_parser("trend", help="Show quality trend dashboard")
    trend_p.add_argument("path", nargs="?", default=".", help="Project directory")
    trend_p.add_argument("--json", action="store_true", help="Output as JSON")
    trend_p.add_argument("--clear", action="store_true", help="Clear trend history")

    # notify
    notify_p = sub.add_parser("notify", help="Send governance report via webhook")
    notify_p.add_argument("path", help="File or directory to check")
    notify_p.add_argument("--webhook", required=True, help="Webhook URL (slack://... or dingtalk://...)")
    notify_p.add_argument("--lang", help="Force language")
    notify_p.add_argument("--project", type=str, default=".", help="Project name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "check": cmd_check,
        "detect": cmd_detect,
        "list-rules": cmd_list_rules,
        "install-hooks": cmd_install_hooks,
        "report": cmd_report,
        "fix": cmd_fix,
        "rule": cmd_rule,
        "trend": cmd_trend,
        "notify": cmd_notify,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
