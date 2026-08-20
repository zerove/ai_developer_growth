"""Core types, constants, and shared helpers for ADG CLI."""

from __future__ import annotations

import json
import os
import sys
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── Configuration ──
_ADG_HOME = Path(os.environ.get("ADG_HOME", Path.home() / ".config" / "adg"))
_RULES_PATH = _ADG_HOME / "rules"

# Fallback: check if ai_developer_growth source is available
_ADG_SOURCE = Path.home() / "dev" / "ai_developer_growth" / "ai-dev-framework"


def _get_rules_path() -> Path:
    """Get the rules directory, preferring config, falling back to source.

    Candidate order: ADG_RULES_DIR env -> GITHUB_WORKSPACE/ai-dev-framework
    -> script-relative/ai-dev-framework -> cwd/ai-dev-framework -> ~/.config/adg/rules -> ~/dev/... source.
    This makes the CLI work both locally and in CI checkouts.
    """
    env_rules = os.environ.get("ADG_RULES_DIR")
    workspace = os.environ.get("GITHUB_WORKSPACE")
    candidates: list[Path] = []
    if env_rules:
        candidates.append(Path(env_rules))
    if workspace:
        candidates.append(Path(workspace) / "ai-dev-framework")
    script_relative = Path(__file__).resolve().parent.parent.parent / "ai-dev-framework"
    candidates.append(script_relative)
    candidates.append(Path.cwd() / "ai-dev-framework")
    candidates += [_RULES_PATH, _ADG_SOURCE]

    for p in candidates:
        if p.exists() and (p / "languages").exists():
            return p
    checked = ", ".join(str(p) for p in candidates)
    print(f"Error: Rules not found (checked: {checked})", file=sys.stderr)
    sys.exit(1)


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
    ".opencode",
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


@dataclass
class Issue:
    """Represents a single code quality issue."""

    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    column: int
    message: str
    fix_hint: str
    related_docs: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }
        if self.related_docs:
            d["related_docs"] = self.related_docs
        return d


# ── Knowledge Base Docs Lookup ─────────────────────────────


def _attach_docs_to_issues(issues: list[Issue]) -> None:
    """Attach related documentation links to issues from the mapping cache."""
    _adg_docs_mapping = Path(__file__).resolve().parent.parent.parent.parent / ".jcode" / "rule-docs-mapping.json"
    if not _adg_docs_mapping.exists():
        return
    try:
        mapping = json.loads(_adg_docs_mapping.read_text())
    except (OSError, json.JSONDecodeError):
        return
    for issue in issues:
        docs = mapping.get(issue.rule_id)
        if docs:
            issue.related_docs = docs


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
        "replacement": None,
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
        "replacement": None,
        "language": "javascript",
    },
    # Rust fixes
    "rust-unwrap": {
        "pattern": r"\.unwrap\(\)",
        "replacement": None,
        "language": "rust",
    },
    # Common fixes
    "common-eval-exec": {
        "pattern": r"\b(eval|exec)\(",
        "replacement": None,
        "language": "common",
    },
    "common-hardcoded-secret": {
        "pattern": r'(SECRET|PASSWORD|API_KEY|TOKEN)\s*=\s*["\'][^"\']+["\']',
        "replacement": None,
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
        "replacement": None,
        "language": "go",
    },
    # TypeScript fixes
    "ts-any": {
        "pattern": r":\s*any\b",
        "replacement": None,
        "language": "typescript",
    },
    "ts-ignore": {
        "pattern": r"//\s*@ts-ignore",
        "replacement": None,
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
        "replacement": None,
        "language": "python",
    },
    "py-mutable-default": {
        "pattern": r"def\s+\w+\(.*?=\s*(\[\]|\{\})\)",
        "replacement": None,
        "language": "python",
    },
}


def _severity_rank(severity: str) -> int:
    """Return numeric rank for severity comparison."""
    return {"error": 0, "warning": 1, "info": 2}.get(severity, 3)


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


def load_project_config(dirpath: Path | None = None) -> dict[str, Any]:
    """Load project-level ADG configuration.

    Looks for:
    1. .adg/rules.yml in project root
    2. ~/.config/adg/rules.yml as global config

    Returns merged configuration with project overriding global.
    """
    from tools.scripts.adg_cli.detect import _simple_yaml_parse

    config: dict[str, Any] = {
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
        except (OSError, yaml.YAMLError):
            pass  # global config optional

    # Load project config (overrides global)
    if dirpath:
        project_config_path = dirpath / ".adg" / "rules.yml"
        if project_config_path.exists():
            try:
                project_config = _simple_yaml_parse(project_config_path)
                if "anti_patterns" in project_config:
                    project_config["custom_rules"] = project_config.pop("anti_patterns")
                config = _merge_config(config, project_config)
            except (OSError, yaml.YAMLError):
                pass  # project config optional

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

_DEFAULT_PRE_COMMIT_HOOK = """#!/bin/bash
# ADG Governance Pre-commit Hook
# Installed by: adg install-hooks

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

CODE_FILES=$(echo "$STAGED_FILES" | grep -E '\\.(py|rs|ts|js|go|java|kt|rb|php|swift|dart|scala)$' || true)

if [ -z "$CODE_FILES" ]; then
    exit 0
fi

echo "🔍 ADG Governance Check on staged files..."

ISSUES=0
ERRORS=0

for FILE in $CODE_FILES; do
    if [ ! -f "$FILE" ]; then
        continue
    fi

    if command -v adg &> /dev/null; then
        OUTPUT=$(adg check "$FILE" 2>&1) || true
    elif [ -x "$HOME/.local/bin/adg" ]; then
        OUTPUT=$($HOME/.local/bin/adg check "$FILE" 2>&1) || true
    else
        echo "⚠️  adg not found. Skipping check."
        exit 0
    fi

    FILE_ERRORS=$(echo "$OUTPUT" | grep -c "error" || true)
    FILE_ISSUES=$(echo "$OUTPUT" | grep -c "warning" || true)

    if [ "$FILE_ERRORS" -gt 0 ]; then
        echo "❌ $FILE: $FILE_ERRORS errors"
        echo "$OUTPUT" | grep "error" | head -5
        ERRORS=$((ERRORS + FILE_ERRORS))
    fi

    if [ "$FILE_ISSUES" -gt 0 ]; then
        echo "⚠️  $FILE: $FILE_ISSUES warnings"
        ISSUES=$((ISSUES + FILE_ISSUES))
    fi
done

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "❌ Governance check failed with $ERRORS errors."
    echo "   Fix errors before committing."
    echo "   Skip: git commit --no-verify"
    exit 1
fi

if [ $ISSUES -gt 0 ]; then
    echo ""
    echo "⚠️  Found $ISSUES warnings (non-blocking)."
fi

echo "✅ Governance check passed."
"""
