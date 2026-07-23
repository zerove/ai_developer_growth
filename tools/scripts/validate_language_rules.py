#!/usr/bin/env python3
"""
Language-Specific Code Quality Validator

Loads machine-readable rules from YAML configs and validates code against:
- Anti-pattern detection (regex-based)
- Naming convention checks
- Quantitative thresholds (function length, nesting depth, etc.)
- Python AST-based analysis (complexity, type annotations)

Usage:
    python validate_language_rules.py <file_or_dir> --lang python
    python validate_language_rules.py <file_or_dir> --auto-detect
    python validate_language_rules.py <file> --lang typescript --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# ──────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────


@dataclass
class Issue:
    """A single validation issue."""

    rule_id: str
    severity: str  # error, warning, info
    category: str
    file: str
    line: int
    message: str
    fix_hint: str = ""
    column: int = 0
    fix_replacement: str = ""  # Auto-fix: regex replacement pattern

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
        if self.fix_replacement:
            d["fix_replacement"] = self.fix_replacement
        return d


@dataclass
class ValidationResult:
    """Aggregated validation results for a file."""

    file: str
    language: str
    issues: list[Issue] = field(default_factory=list)
    lines_checked: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "language": self.language,
            "passed": self.passed,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "lines_checked": self.lines_checked,
            "issues": [i.to_dict() for i in self.issues],
        }


# ──────────────────────────────────────────────────────────
@dataclass
class FixResult:
    """Result of an auto-fix operation."""

    file: str
    rule_id: str
    line: int
    original: str
    fixed: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "rule_id": self.rule_id,
            "line": self.line,
            "original": self.original,
            "fixed": self.fixed,
            "description": self.description,
        }


@dataclass
class HealthScore:
    """Project health score (0-100)."""

    score: int
    grade: str
    breakdown: dict[str, float]
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "grade": self.grade,
            "breakdown": self.breakdown,
            "details": self.details,
        }


# Rule loader
# ──────────────────────────────────────────────────────────


def load_rules(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load YAML rules for a given language."""
    if yaml is None:
        print("Warning: PyYAML not installed. Using embedded rules.", file=sys.stderr)
        return _get_embedded_rules(language)

    if framework_dir is None:
        framework_dir = Path(__file__).parent.parent.parent / "ai-dev-framework"

    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    if not rule_path.exists():
        print(f"Warning: Rules not found at {rule_path}, using embedded rules.", file=sys.stderr)
        return _get_embedded_rules(language)

    with open(rule_path) as f:
        data = yaml.safe_load(f)

    return data if isinstance(data, dict) else {}


def load_custom_rules(project_dir: Path) -> dict[str, Any]:
    """Load custom rules from .ai-rules/*.yml in the project directory.

    Custom rules extend (not replace) built-in rules.
    Rules with the same ID override built-in rules.
    """
    custom: dict[str, Any] = {"anti_patterns": [], "naming": {}, "thresholds": {}}
    rules_dir = project_dir / ".ai-rules"

    if not rules_dir.is_dir():
        return custom

    if yaml is None:
        print("Warning: PyYAML not installed. Custom rules skipped.", file=sys.stderr)
        return custom

    for rule_file in sorted(rules_dir.glob("*.yml")):
        try:
            with open(rule_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue

            # Merge anti_patterns (override by ID)
            new_patterns = data.get("anti_patterns", [])
            custom["anti_patterns"].extend(new_patterns)

            # Merge naming rules
            if "naming" in data:
                custom["naming"].update(data["naming"])

            # Merge thresholds (override)
            if "thresholds" in data:
                custom["thresholds"].update(data["thresholds"])

        except Exception as e:
            print(f"Warning: Failed to load {rule_file}: {e}", file=sys.stderr)

    return custom


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules. Custom overrides by ID."""
    merged = dict(base)

    # Merge anti_patterns: custom overrides by ID, then appends new ones
    base_patterns = merged.get("anti_patterns", [])
    custom_patterns = custom.get("anti_patterns", [])

    if custom_patterns:
        base_ids = {p["id"] for p in base_patterns}
        overridden = []
        new_only = []
        for cp in custom_patterns:
            if cp.get("id") in base_ids:
                overridden.append(cp)
            else:
                new_only.append(cp)

        # Replace overridden patterns
        merged_patterns = [next((cp for cp in overridden if cp["id"] == p["id"]), p) for p in base_patterns]
        merged_patterns.extend(new_only)
        merged["anti_patterns"] = merged_patterns

    # Merge naming
    if custom.get("naming"):
        merged.setdefault("naming", {}).update(custom["naming"])

    # Merge thresholds
    if custom.get("thresholds"):
        merged.setdefault("thresholds", {}).update(custom["thresholds"])

    return merged


def _get_embedded_rules(language: str) -> dict[str, Any]:
    """Fallback embedded rules when YAML files are unavailable."""
    common_anti_patterns: list[dict[str, Any]] = [
        {
            "id": f"{language[:2]}-eval-exec",
            "name": "Use of eval/exec",
            "severity": "error",
            "category": "security",
            "pattern": r"\beval\s*\(|\bexec\s*\(",
            "message": "eval/exec are security risks",
            "fix_hint": "Find a safer alternative",
        },
        {
            "id": f"{language[:2]}-hardcoded-secret",
            "name": "Hardcoded secret",
            "severity": "error",
            "category": "security",
            "pattern": r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            "message": "Hardcoded secrets are a security vulnerability",
            "fix_hint": "Use environment variables",
        },
    ]
    return {"anti_patterns": common_anti_patterns, "thresholds": {}, "naming": {}}


# ──────────────────────────────────────────────────────────
# Regex anti-pattern checker
# ──────────────────────────────────────────────────────────


def check_anti_patterns(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check code lines against regex anti-patterns."""
    issues: list[Issue] = []
    anti_patterns = rules.get("anti_patterns", [])

    for pattern_def in anti_patterns:
        regex = re.compile(pattern_def["pattern"])

        for line_num, line in enumerate(lines, 1):
            # Skip comments and strings (basic heuristic)
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            match = regex.search(line)
            if match:
                issues.append(
                    Issue(
                        rule_id=pattern_def["id"],
                        severity=pattern_def.get("severity", "warning"),
                        category=pattern_def.get("category", "general"),
                        file=filepath,
                        line=line_num,
                        column=match.start(),
                        message=pattern_def.get("message", "Anti-pattern detected"),
                        fix_hint=pattern_def.get("fix_hint", ""),
                    )
                )

    return issues


# ──────────────────────────────────────────────────────────
# Naming convention checker
# ──────────────────────────────────────────────────────────


def check_naming_conventions(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check naming conventions based on language rules."""
    issues: list[Issue] = []
    naming = rules.get("naming", {})
    language = rules.get("language", "")

    # Check filename
    file_rule = naming.get("file", {})
    if file_rule and "pattern" in file_rule:
        filename = Path(filepath).name
        if not re.match(file_rule["pattern"], filename):
            issues.append(
                Issue(
                    rule_id=f"{language[:2]}-naming-file",
                    severity="warning",
                    category="naming",
                    file=filepath,
                    line=0,
                    message=file_rule.get("message", f"File name '{filename}' violates naming convention"),
                )
            )

    # Check function/class/variable names in code
    for kind in ["function", "class", "struct", "enum", "constant", "interface", "module", "trait", "package"]:
        kind_rule = naming.get(kind, {})
        if not kind_rule or "pattern" not in kind_rule:
            continue

        regex = re.compile(kind_rule["pattern"])
        exceptions = kind_rule.get("exceptions", [])

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            # Extract identifier based on language patterns
            identifiers = _extract_identifiers(stripped, kind, language)

            for ident in identifiers:
                if ident in exceptions:
                    continue
                if not regex.match(ident):
                    issues.append(
                        Issue(
                            rule_id=f"{language[:2]}-naming-{kind}",
                            severity="info",
                            category="naming",
                            file=filepath,
                            line=line_num,
                            message=kind_rule.get("message", f"'{ident}' violates {kind} naming convention"),
                        )
                    )

    return issues


def _extract_identifiers(line: str, kind: str, language: str) -> list[str]:
    """Extract identifiers from a line based on the kind and language."""
    identifiers: list[str] = []

    if language == "python":
        if kind == "function":
            m = re.match(r"(?:async\s+)?def\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"class\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=", line)
            if m:
                identifiers.append(m.group(1))

    elif language in ("typescript", "ts"):
        if kind == "function":
            m = re.match(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:export\s+)?class\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "interface":
            m = re.match(r"(?:export\s+)?interface\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:export\s+)?const\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "rust":
        if kind == "function":
            m = re.match(r"(?:pub\s+)?(?:async\s+)?fn\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind in ("struct", "enum", "trait"):
            m = re.match(r"(?:pub\s+)?(?:struct|enum|trait)\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:pub\s+)?const\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "module":
            m = re.match(r"mod\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "go":
        if kind == "function":
            m = re.match(r"func\s+(?:\([^)]+\)\s+)?([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind in ("struct", "interface"):
            m = re.match(r"type\s+([a-zA-Z_]\w*)\s+(?:struct|interface)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:const|var)\s+([a-zA-Z_]\w*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "package":
            m = re.match(r"package\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "java":
        if kind == "function":
            m = re.match(
                r"(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:<[^>]+>\s+)?(\w+)\s+\w+\s*\(",
                line,
            )
            if m and m.group(1) not in ("if", "for", "while", "switch", "catch", "try", "return", "new", "throw"):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:public|private|protected)?\s*(?:abstract\s+)?(?:final\s+)?class\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:public|private|protected)?\s*static\s+final\s+\w+\s+([A-Z][A-Z0-9_]*)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "package":
            m = re.match(r"package\s+([\w.]+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "kotlin":
        if kind == "function":
            m = re.match(r"(?:fun|suspend\s+fun)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:data\s+)?(?:abstract\s+)?(?:open\s+)?class\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"const\s+val\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "csharp":
        if kind == "function":
            m = re.match(
                r"(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:\w+\s+)?(\w+)\s*\(", line
            )
            if m and m.group(1) not in (
                "if",
                "for",
                "while",
                "switch",
                "catch",
                "try",
                "return",
                "new",
                "throw",
                "using",
            ):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(
                r"(?:public|private|protected|internal)?\s*(?:abstract\s+)?(?:sealed\s+)?(?:partial\s+)?class\s+(\w+)",
                line,
            )
            if m:
                identifiers.append(m.group(1))
        elif kind == "interface":
            m = re.match(r"(?:public|private|protected|internal)?\s*(?:partial\s+)?interface\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:public|private|protected|internal)?\s*const\s+\w+\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "php":
        if kind == "function":
            m = re.match(r"(?:public|private|protected)?\s*(?:static\s+)?function\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:abstract\s+)?class\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:public|private|protected)?\s*const\s+([A-Z][A-Z0-9_]*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "ruby":
        if kind == "function":
            m = re.match(r"(?:def|defself)\s+(\w+[!?]?)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind in ("class", "module"):
            m = re.match(r"(?:class|module)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"([A-Z][A-Z0-9_]*)\s*=", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "cpp":
        if kind == "function":
            m = re.match(r"(?:[\w:*&<>\s]+?)\s+(\w+)\s*\(", line)
            if m and m.group(1) not in (
                "if",
                "for",
                "while",
                "switch",
                "catch",
                "try",
                "return",
                "new",
                "delete",
                "sizeof",
                "typeof",
            ):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:class|struct)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:const|constexpr|static\s+const)\s+\w+\s+([A-Z][A-Z0-9_]*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "swift":
        if kind == "function":
            m = re.match(r"(?:func|static\s+func)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:class|struct|enum|protocol)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:let|static\s+let)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "scala":
        if kind == "function":
            m = re.match(r"(?:def|override\s+def)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:class|trait|object)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"val\s+([A-Z][A-Z0-9_]*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "elixir":
        if kind == "function":
            m = re.match(r"(?:defp?|defmacrop?)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"defmodule\s+([\w.]+)", line)
            if m:
                identifiers.append(m.group(1).split(".")[-1])
        elif kind == "constant":
            m = re.match(r"(@?[A-Z][A-Z0-9_]*)\s*=", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "lua":
        if kind == "function":
            m = re.match(r"(?:local\s+)?function\s+([\w.]+)", line)
            if m:
                identifiers.append(m.group(1).split(".")[-1])
        elif kind == "class":
            m = re.match(r"(?:local\s+)?(\w+)\s*=\s*\{\s*\}", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"([A-Z][A-Z0-9_]*)\s*=", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "javascript":
        if kind == "function":
            m = re.match(r"(?:export\s+)?(?:async\s+)?(?:function|const|let|var)\s+(\w+)", line)
            if m and m.group(1) not in (
                "if",
                "for",
                "while",
                "switch",
                "catch",
                "try",
                "return",
                "new",
                "delete",
                "typeof",
                "instanceof",
            ):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:export\s+)?class\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:export\s+)?const\s+([A-Z][A-Z0-9_]*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "zig":
        if kind == "function":
            m = re.match(r"(?:pub\s+)?(?:inline\s+)?fn\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind in ("class", "struct", "enum"):
            m = re.match(r"(?:pub\s+)?(?:const|var)\s+(\w+)\s*=\s*(?:struct|enum|union)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:pub\s+)?const\s+([A-Z][A-Z0-9_]*)\s*=", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "r":
        if kind == "function":
            m = re.match(r"(\w+)\s*(?:<-|=)\s*function\s*\(", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(\w+)\s*(?:<-|=)\s*setClass\(", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"([A-Z][A-Z0-9_]*)\s*(?:<-|=)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "clojure":
        if kind == "function":
            m = re.match(r"\(defn-?\s+(\S+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"\(defrecord\s+(\S+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"\(def\s+([A-Z][A-Z0-9_-]*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "haskell":
        if kind == "function":
            m = re.match(r"(\w+)\s*(?:::|[=])", line)
            if m and m.group(1) not in ("where", "let", "in", "if", "then", "else", "case", "of", "do"):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:data|newtype|type)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(\w+)\s*::\s*\w+", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "dart":
        if kind == "function":
            m = re.match(r"(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(", line)
            if m and m.group(1) not in (
                "if",
                "for",
                "while",
                "switch",
                "catch",
                "try",
                "return",
                "new",
                "delete",
                "class",
                "extends",
                "implements",
                "import",
                "export",
            ):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:abstract\s+)?class\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:static\s+)?const\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "powershell":
        if kind == "function":
            m = re.match(r"function\s+([\w-]+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"class\s+([\w.]+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"\$([A-Z][A-Z0-9_]*)\s*=", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "perl":
        if kind == "function":
            m = re.match(r"(?:sub|method)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"our\s+([A-Z][A-Z0-9_]*)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "assembly":
        if kind == "function":
            m = re.match(r"^(\w+):", line)
            if m and not m.group(1).startswith("."):
                identifiers.append(m.group(1))

    elif language == "fortran":
        if kind == "function":
            m = re.match(r"(?:subroutine|function)\s+(\w+)", line, re.IGNORECASE)
            if m:
                identifiers.append(m.group(1))
        elif kind == "constant":
            m = re.match(r"(?:parameter|PARAMETER)\s*\((\w+)\s*=", line, re.IGNORECASE)
            if m:
                identifiers.append(m.group(1))

    elif language == "graphql":
        if kind == "function":
            m = re.match(r"(?:type|input|interface)\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    elif language == "matlab":
        if kind == "function":
            m = re.match(r"function\s+.*?(\w+)\s*\(", line)
            if m:
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"classdef\s+(\w+)", line)
            if m:
                identifiers.append(m.group(1))

    return identifiers


# ──────────────────────────────────────────────────────────
# Threshold checker
# ──────────────────────────────────────────────────────────


def check_thresholds(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check quantitative thresholds."""
    issues: list[Issue] = []
    thresholds = rules.get("thresholds", {})
    language = rules.get("language", "")

    # Line length
    max_line = thresholds.get("max_line_length", 120)
    for line_num, line in enumerate(lines, 1):
        if len(line.rstrip()) > max_line:
            issues.append(
                Issue(
                    rule_id=f"{language[:2]}-threshold-line-length",
                    severity="info",
                    category="readability",
                    file=filepath,
                    line=line_num,
                    message=f"Line length {len(line.rstrip())} exceeds {max_line}",
                )
            )

    # File length
    max_file = thresholds.get("max_file_length", 500)
    if len(lines) > max_file:
        issues.append(
            Issue(
                rule_id=f"{language[:2]}-threshold-file-length",
                severity="warning",
                category="readability",
                file=filepath,
                line=0,
                message=f"File has {len(lines)} lines (max {max_file})",
            )
        )

    # Function length and nesting depth
    max_func = thresholds.get("max_function_length", 50)
    max_nest = thresholds.get("max_nesting_depth", 4)

    func_lines = _extract_function_lines(lines, language)
    for func_name, start, end in func_lines:
        length = end - start + 1
        if length > max_func:
            issues.append(
                Issue(
                    rule_id=f"{language[:2]}-threshold-func-length",
                    severity="warning",
                    category="readability",
                    file=filepath,
                    line=start,
                    message=f"Function '{func_name}' is {length} lines (max {max_func})",
                )
            )

        # Check nesting depth within function
        depth = _max_nesting_depth(lines[start - 1 : end], language)
        if depth > max_nest:
            issues.append(
                Issue(
                    rule_id=f"{language[:2]}-threshold-nesting",
                    severity="warning",
                    category="readability",
                    file=filepath,
                    line=start,
                    message=f"Function '{func_name}' has nesting depth {depth} (max {max_nest})",
                )
            )

    return issues


def _extract_function_lines(lines: list[str], language: str) -> list[tuple[str, int, int]]:
    """Extract function name, start line, end line."""
    functions: list[tuple[str, int, int]] = []

    if language == "python":
        try:
            tree = ast.parse("\n".join(lines))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = node.lineno
                    end = getattr(node, "end_lineno", start + 50)
                    functions.append((node.name, start, end))
        except SyntaxError:
            pass

    elif language in ("typescript", "ts", "rust", "go"):
        # Regex-based function detection for non-Python
        patterns = {
            "typescript": [
                r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
                r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(",
            ],
            "rust": [r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"],
            "go": [r"func\s+(?:\([^)]+\)\s+)?(\w+)"],
        }
        for pattern in patterns.get(language, []):
            for match in re.finditer(pattern, "\n".join(lines)):
                name = match.group(1)
                start = "\n".join(lines[: match.start()]).count("\n") + 1
                # Estimate end by finding next top-level definition
                end = min(start + 50, len(lines))
                functions.append((name, start, end))

    return functions


def _max_nesting_depth(lines: list[str], language: str = "") -> int:
    """Calculate maximum nesting depth from lines."""
    if language == "python":
        return _max_python_indent_depth(lines)

    max_depth = 0
    current_depth = 0
    for line in lines:
        stripped = line.strip()
        for ch in stripped:
            if ch in "({[":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif ch in ")}]":
                current_depth = max(0, current_depth - 1)
    return max_depth


def _max_python_indent_depth(lines: list[str]) -> int:
    """Calculate max nesting depth for Python using indentation."""
    max_depth = 0
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        depth = indent // 4  # 4-space indentation
        max_depth = max(max_depth, depth)
    return max_depth


# ──────────────────────────────────────────────────────────
# Python AST checks
# ──────────────────────────────────────────────────────────


def check_python_ast(filepath: str, lines: list[str]) -> list[Issue]:
    """Python-specific AST-based checks."""
    issues: list[Issue] = []

    try:
        source = "\n".join(lines)
        tree = ast.parse(source)
    except SyntaxError as e:
        issues.append(
            Issue(
                rule_id="py-ast-syntax-error",
                severity="error",
                category="syntax",
                file=filepath,
                line=e.lineno or 1,
                message=f"Syntax error: {e.msg}",
            )
        )
        return issues

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_python_function(node, filepath, issues)

    return issues


def _check_python_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: str,
    issues: list[Issue],
) -> None:
    """Check a Python function node for quality issues."""
    name = node.name

    # Check return type annotation
    if node.returns is None and not name.startswith("_"):
        issues.append(
            Issue(
                rule_id="py-ast-no-return-type",
                severity="info",
                category="type_safety",
                file=filepath,
                line=node.lineno,
                message=f"Public function '{name}' lacks return type annotation",
            )
        )

    # Check parameter type annotations
    for arg in node.args.args:
        if arg.annotation is None and arg.arg != "self" and arg.arg != "cls":
            issues.append(
                Issue(
                    rule_id="py-ast-no-param-type",
                    severity="info",
                    category="type_safety",
                    file=filepath,
                    line=node.lineno,
                    message=f"Parameter '{arg.arg}' of '{name}' lacks type annotation",
                )
            )

    # Check function length
    if hasattr(node, "end_lineno") and node.end_lineno:
        length = node.end_lineno - node.lineno + 1
        if length > 50:
            issues.append(
                Issue(
                    rule_id="py-ast-function-length",
                    severity="warning",
                    category="readability",
                    file=filepath,
                    line=node.lineno,
                    message=f"Function '{name}' is {length} lines (max 50)",
                )
            )

    # Check argument count
    args = node.args
    total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
    # Subtract 'self' and 'cls'
    if args.args and args.args[0].arg in ("self", "cls"):
        total_args -= 1
    if total_args > 7:
        issues.append(
            Issue(
                rule_id="py-ast-function-args",
                severity="warning",
                category="readability",
                file=filepath,
                line=node.lineno,
                message=f"Function '{name}' has {total_args} arguments (max 7)",
            )
        )

    # Check cyclomatic complexity
    complexity = _calc_cyclomatic_complexity(node)
    if complexity >= 10:
        issues.append(
            Issue(
                rule_id="py-ast-complexity",
                severity="warning",
                category="readability",
                file=filepath,
                line=node.lineno,
                message=f"Function '{name}' has cyclomatic complexity {complexity} (max 10)",
            )
        )


def _calc_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity for an AST node."""
    complexity = 1

    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, (ast.With, ast.AsyncWith)):
            complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1

    return complexity


# ──────────────────────────────────────────────────────────
# Auto-fix engine (#1)
# ──────────────────────────────────────────────────────────


def apply_fixes(filepath: Path, issues: list[Issue], dry_run: bool = False) -> list[FixResult]:
    """Apply auto-fixes to a file based on issues with fix_replacement.

    Args:
        filepath: File to fix
        issues: Issues to fix (only those with fix_replacement set)
        dry_run: If True, report what would change without writing

    Returns:
        List of FixResult describing each change
    """
    fixes: list[FixResult] = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return fixes

    lines = content.splitlines(keepends=True)
    modified = False

    for issue in issues:
        if not issue.fix_replacement or issue.line < 1 or issue.line > len(lines):
            continue

        line_idx = issue.line - 1
        original_line = lines[line_idx]

        # Try regex replacement on the line
        try:
            # fix_replacement format: "s/pattern/replacement/flags" or literal string
            replacement = issue.fix_replacement
            if replacement.startswith("s/") and replacement.count("/") >= 3:
                # sed-style: s/pattern/replacement/flags
                parts = replacement.split("/")
                pattern = parts[1]
                new_text = parts[2]
                flags = parts[3] if len(parts) > 3 else ""
                re_flags = re.IGNORECASE if "i" in flags else 0
                new_line = re.sub(pattern, new_text, original_line, flags=re_flags)
            else:
                # Literal replacement of matched text
                new_line = original_line.replace(
                    issue.message.split(":")[-1].strip() if ":" in issue.message else "",
                    replacement,
                    1,
                )

            if new_line != original_line:
                fixes.append(
                    FixResult(
                        file=str(filepath),
                        rule_id=issue.rule_id,
                        line=issue.line,
                        original=original_line.rstrip(),
                        fixed=new_line.rstrip(),
                        description=issue.fix_hint or f"Auto-fixed: {issue.rule_id}",
                    )
                )
                if not dry_run:
                    lines[line_idx] = new_line
                    modified = True
        except re.error:
            continue

    if modified and not dry_run:
        filepath.write_text("".join(lines), encoding="utf-8")

    return fixes


# ──────────────────────────────────────────────────────────
# Report generators (#6)
# ──────────────────────────────────────────────────────────


def generate_junit_xml(results: list[ValidationResult]) -> str:
    """Generate JUnit XML report."""
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_tests = len(results)
    failures = sum(1 for r in results if not r.passed)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="language-rules" tests="{total_tests}" '
        f'failures="{failures}" errors="{total_errors}" warnings="{total_warnings}">',
    ]

    for result in results:
        testcase = f'  <testcase name="{_xml_escape(result.file)}" classname="{result.language}">'
        if not result.passed:
            for issue in result.issues:
                if issue.severity == "error":
                    lines.append(f"{testcase}")
                    lines.append(f'    <failure message="{_xml_escape(issue.message)}">')
                    lines.append(f"      {issue.rule_id}: {issue.message} (line {issue.line})")
                    lines.append("    </failure>")
                    lines.append("  </testcase>")
                    break
            else:
                lines.append(f"{testcase}</testcase>")
        else:
            # Report warnings as system-out
            warns = [i for i in result.issues if i.severity == "warning"]
            if warns:
                lines.append(f"{testcase}")
                lines.append("    <system-out>")
                for w in warns[:5]:
                    lines.append(f"      [{w.rule_id}] {w.message} (line {w.line})")
                lines.append("    </system-out>")
                lines.append("  </testcase>")
            else:
                lines.append(f"{testcase}</testcase>")

    lines.append("</testsuite>")
    return "\n".join(lines)


def _xml_escape(s: str) -> str:
    """Escape XML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html_report(results: list[ValidationResult]) -> str:
    """Generate HTML report."""
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)
    passed_count = sum(1 for r in results if r.passed)

    rows = []
    for result in sorted(results, key=lambda r: (not r.passed, r.file)):
        status_class = "pass" if result.passed else "fail"
        rows.append(f"""      <tr class="{status_class}">
        <td>{_html_escape(result.file)}</td>
        <td>{result.language}</td>
        <td class="num">{result.error_count}</td>
        <td class="num">{result.warning_count}</td>
        <td class="num">{result.info_count}</td>
        <td>{"PASS" if result.passed else "FAIL"}</td>
      </tr>""")
        if not result.passed:
            for issue in result.issues[:3]:
                rows.append(f"""      <tr class="detail">
        <td colspan="6">[{issue.severity}] {issue.rule_id}: {_html_escape(issue.message)} (line {issue.line})</td>
      </tr>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Language Rules Report</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
    .summary {{ display: flex; gap: 2rem; margin-bottom: 2rem; }}
    .card {{ padding: 1rem 1.5rem; border-radius: 8px; }}
    .card.error {{ background: #fee; border: 1px solid #fcc; }}
    .card.warn {{ background: #ffd; border: 1px solid #ff8; }}
    .card.pass {{ background: #efe; border: 1px solid #8c8; }}
    .card.info {{ background: #eef; border: 1px solid #88c; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ padding: 0.5rem 1rem; border: 1px solid #ddd; text-align: left; }}
    th {{ background: #f5f5f5; }}
    tr.pass td {{ background: #efe; }}
    tr.fail td {{ background: #fee; }}
    tr.detail td {{ background: #f9f9f9; font-size: 0.9em; color: #666; }}
    .num {{ text-align: right; }}
  </style>
</head>
<body>
  <h1>Language Rules Report</h1>
  <div class="summary">
    <div class="card pass"><strong>{passed_count}</strong> files passed</div>
    <div class="card error"><strong>{total_errors}</strong> errors</div>
    <div class="card warn"><strong>{total_warnings}</strong> warnings</div>
    <div class="card info"><strong>{total_info}</strong> info</div>
  </div>
  <table>
    <tr><th>File</th><th>Language</th><th>Errors</th><th>Warnings</th><th>Info</th><th>Status</th></tr>
{chr(10).join(rows)}
  </table>
</body>
</html>"""


def _html_escape(s: str) -> str:
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_report(results: list[ValidationResult], format: str, output: Path | None = None) -> str | None:
    """Write report in specified format. Returns content or writes to file."""
    if format == "json":
        data = {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total_files": len(results),
                "total_errors": sum(r.error_count for r in results),
                "total_warnings": sum(r.warning_count for r in results),
                "total_info": sum(r.info_count for r in results),
                "passed": all(r.passed for r in results),
            },
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
    elif format == "junit":
        content = generate_junit_xml(results)
    elif format == "html":
        content = generate_html_report(results)
    else:
        return None

    if output:
        output.write_text(content, encoding="utf-8")
        print(f"Report written to {output}", file=sys.stderr)
    return content


# ──────────────────────────────────────────────────────────
# Health score (#10)
# ──────────────────────────────────────────────────────────


def calculate_health_score(results: list[ValidationResult]) -> HealthScore:
    """Calculate project health score (0-100) from validation results.

    Scoring:
    - Base: 100
    - Each error: -5 points
    - Each warning: -2 points
    - Each info: -0.5 points
    - Bonus: +2 per clean file (max +10)
    - Penalty for file-level failures: -3 per failed file
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)
    total_files = len(results)
    failed_files = sum(1 for r in results if not r.passed)
    clean_files = total_files - failed_files

    # Base score
    score = 100.0

    # Penalties
    score -= total_errors * 5.0
    score -= total_warnings * 2.0
    score -= total_info * 0.5
    score -= failed_files * 3.0

    # Bonus for clean files
    bonus = min(clean_files * 2, 10)
    score += bonus

    # Clamp
    score = max(0, min(100, round(score)))

    # Grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    # Breakdown
    breakdown = {
        "error_penalty": total_errors * -5.0,
        "warning_penalty": total_warnings * -2.0,
        "info_penalty": total_info * -0.5,
        "failure_penalty": failed_files * -3.0,
        "clean_bonus": bonus,
    }

    # Details
    details = []
    if total_errors > 0:
        details.append(f"{total_errors} errors found (-{total_errors * 5} points)")
    if total_warnings > 0:
        details.append(f"{total_warnings} warnings found (-{total_warnings * 2} points)")
    if failed_files > 0:
        details.append(f"{failed_files} files failed (-{failed_files * 3} points)")
    if clean_files > 0:
        details.append(f"{clean_files} files clean (+{bonus} points)")
    if not details:
        details.append("All files clean")

    return HealthScore(score=score, grade=grade, breakdown=breakdown, details=details)


# ──────────────────────────────────────────────────────────
# Linter aggregation (#9)
# ──────────────────────────────────────────────────────────


def run_linter_aggregation(
    dirpath: Path,
    linters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run external linters and aggregate results into unified format.

    Supported linters: ruff, mypy, eslint, golangci-lint
    Returns list of unified issue dicts.
    """

    if linters is None:
        linters = []

    unified: list[dict[str, Any]] = []

    for linter in linters:
        if linter == "ruff":
            unified.extend(_run_ruff(dirpath))
        elif linter == "mypy":
            unified.extend(_run_mypy(dirpath))
        elif linter == "eslint":
            unified.extend(_run_eslint(dirpath))
        elif linter == "golangci-lint":
            unified.extend(_run_golangci(dirpath))

    return unified


def _run_ruff(dirpath: Path) -> list[dict[str, Any]]:
    """Run ruff and parse results."""
    import subprocess

    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for item in data:
                issues.append(
                    {
                        "linter": "ruff",
                        "rule_id": item.get("code", ""),
                        "severity": "error" if item.get("fix") is None else "warning",
                        "file": item.get("filename", ""),
                        "line": item.get("location", {}).get("row", 0),
                        "message": item.get("message", ""),
                    }
                )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return issues


def _run_mypy(dirpath: Path) -> list[dict[str, Any]]:
    """Run mypy and parse results."""
    import subprocess

    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["mypy", "--ignore-missing-imports", "--no-error-summary", "--show-error-codes", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        for line in result.stdout.splitlines():
            if ": error:" in line:
                parts = line.split(": ", 2)
                if len(parts) >= 3:
                    file_line = parts[0]
                    msg = parts[1]
                    code = parts[2] if len(parts) > 2 else ""
                    fl = file_line.rsplit(":", 1)
                    issues.append(
                        {
                            "linter": "mypy",
                            "rule_id": code.strip("()"),
                            "severity": "error",
                            "file": fl[0] if len(fl) > 1 else str(dirpath),
                            "line": int(fl[1]) if fl[1].isdigit() else 0,
                            "message": msg,
                        }
                    )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return issues


def _run_eslint(dirpath: Path) -> list[dict[str, Any]]:
    """Run eslint and parse results."""
    import subprocess

    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["eslint", "--format=json", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for file_entry in data:
                for msg in file_entry.get("messages", []):
                    issues.append(
                        {
                            "linter": "eslint",
                            "rule_id": msg.get("ruleId", ""),
                            "severity": "error" if msg.get("severity") == 2 else "warning",
                            "file": file_entry.get("filePath", ""),
                            "line": msg.get("line", 0),
                            "message": msg.get("message", ""),
                        }
                    )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return issues


def _run_golangci(dirpath: Path) -> list[dict[str, Any]]:
    """Run golangci-lint and parse results."""
    import subprocess

    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["golangci-lint", "run", "--out-format=json", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for issue in data.get("Issues", []):
                issues.append(
                    {
                        "linter": "golangci-lint",
                        "rule_id": issue.get("FromLinter", ""),
                        "severity": "error",
                        "file": issue.get("Pos", {}).get("Filename", ""),
                        "line": issue.get("Pos", {}).get("Line", 0),
                        "message": issue.get("Text", ""),
                    }
                )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return issues


# ──────────────────────────────────────────────────────────
# Main validation
# ──────────────────────────────────────────────────────────


def validate_file(
    filepath: Path,
    language: str,
    custom_rules: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate a single file against language rules."""
    result = ValidationResult(file=str(filepath), language=language)

    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        result.issues.append(
            Issue(
                rule_id="read-error",
                severity="error",
                category="io",
                file=str(filepath),
                line=0,
                message=f"Cannot read file: {e}",
            )
        )
        return result

    result.lines_checked = len(lines)
    rules = load_rules(language)

    # Merge custom rules if provided
    if custom_rules and (custom_rules.get("anti_patterns") or custom_rules.get("thresholds")):
        rules = _merge_rules(rules, custom_rules)

    # 1. Regex anti-pattern checks (with fix_replacement support)
    anti_issues = check_anti_patterns(lines, rules, str(filepath))
    # Propagate fix_replacement from rule definitions
    pattern_map = {p["id"]: p for p in rules.get("anti_patterns", [])}
    for issue in anti_issues:
        rule_def = pattern_map.get(issue.rule_id, {})
        if "fix_replacement" in rule_def:
            issue.fix_replacement = rule_def["fix_replacement"]
    result.issues.extend(anti_issues)

    # 2. Naming convention checks
    result.issues.extend(check_naming_conventions(lines, rules, str(filepath)))

    # 3. Threshold checks
    result.issues.extend(check_thresholds(lines, rules, str(filepath)))

    # 4. Language-specific AST checks
    if language == "python":
        result.issues.extend(check_python_ast(str(filepath), lines))

    return result


# File extensions to language mapping
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
    ".scala": "scala",
    ".ex": "elixir",
    ".exs": "elixir",
    ".lua": "lua",
    ".zig": "zig",
    ".r": "r",
    ".R": "r",
    ".clj": "clojure",
    ".hs": "haskell",
    ".dart": "dart",
    ".ps1": "powershell",
    ".pl": "perl",
    ".pm": "perl",
    ".asm": "assembly",
    ".s": "assembly",
    ".S": "assembly",
    ".f90": "fortran",
    ".f": "fortran",
    ".for": "fortran",
    ".m": "matlab",
    ".graphql": "graphql",
    ".gql": "graphql",
}


def detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


def validate_directory(
    dirpath: Path,
    language: str | None = None,
    exclude: list[str] | None = None,
    custom_rules: dict[str, Any] | None = None,
) -> list[ValidationResult]:
    """Validate all supported files in a directory."""
    results: list[ValidationResult] = []
    exclude = exclude or ["node_modules", "target", "vendor", ".git", "__pycache__", ".venv"]

    for filepath in sorted(dirpath.rglob("*")):
        if not filepath.is_file():
            continue

        # Skip excluded directories
        if any(ex in filepath.parts for ex in exclude):
            continue

        file_lang = language or detect_language_from_file(filepath)
        if file_lang is None:
            continue

        results.append(validate_file(filepath, file_lang, custom_rules=custom_rules))

    return results


# ──────────────────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────────────────

SEVERITY_ICONS = {"error": "error", "warning": "warning", "info": "info"}


def print_results(results: list[ValidationResult], use_json: bool = False) -> int:
    """Print validation results. Returns exit code (0=pass)."""
    if use_json:
        output = {
            "results": [r.to_dict() for r in results],
            "total_files": len(results),
            "total_errors": sum(r.error_count for r in results),
            "total_warnings": sum(r.warning_count for r in results),
            "total_info": sum(r.info_count for r in results),
            "passed": all(r.passed for r in results),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0 if output["passed"] else 1

    total_errors = 0
    total_warnings = 0

    for result in results:
        if not result.issues:
            continue

        print(f"\n  {result.file} ({result.language}, {result.lines_checked} lines)")

        for issue in sorted(result.issues, key=lambda x: (x.severity, x.line)):
            icon = SEVERITY_ICONS.get(issue.severity, "?")
            loc = f":{issue.line}" if issue.line > 0 else ""
            print(f"    {icon} [{issue.rule_id}] {issue.message}{loc}")
            if issue.fix_hint:
                print(f"      -> {issue.fix_hint}")

            if issue.severity == "error":
                total_errors += 1
            elif issue.severity == "warning":
                total_warnings += 1

    # Summary
    print("\n  Summary:")
    print(f"    Files checked: {len(results)}")
    print(f"    Errors:   {total_errors}")
    print(f"    Warnings: {total_warnings}")

    if total_errors > 0:
        print("\n  FAILED - errors must be fixed")
        return 1
    elif total_warnings > 0:
        print("\n  PASSED with warnings")
        return 0
    else:
        print("\n  PASSED - all checks clean")
        return 0


# ──────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Language-specific code quality validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s src/ --lang python
  %(prog)s lib/ --lang typescript --format json -o report.json
  %(prog)s . --auto-detect --format html -o report.html
  %(prog)s main.rs --lang rust --fix --dry-run
  %(prog)s . --auto-detect --max-errors 0 --max-warnings 10
  %(prog)s . --auto-detect --linters ruff mypy
  %(prog)s . --auto-detect --health-score
  %(prog)s . --auto-detect --custom-rules .ai-rules/
        """,
    )
    parser.add_argument("path", type=Path, help="File or directory to validate")
    parser.add_argument(
        "--lang",
        choices=[
            "python",
            "typescript",
            "rust",
            "go",
            "java",
            "kotlin",
            "csharp",
            "php",
            "ruby",
            "cpp",
            "swift",
            "scala",
            "elixir",
            "lua",
            "javascript",
            "zig",
            "r",
            "clojure",
            "haskell",
            "dart",
            "powershell",
            "perl",
            "assembly",
            "fortran",
            "matlab",
            "graphql",
        ],
        help="Language to validate against",
    )
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect language from file extensions")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output results as JSON (legacy)")
    parser.add_argument("--fail-on-warnings", action="store_true", help="Exit with error on warnings")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["node_modules", "target", "vendor", ".git", "__pycache__", ".venv"],
        help="Directories to exclude",
    )

    # New: Report format (#6)
    parser.add_argument(
        "--format",
        choices=["text", "json", "html", "junit"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("-o", "--output", type=Path, help="Write report to file")

    # New: Severity thresholds (#7)
    parser.add_argument("--max-errors", type=int, default=None, help="Max allowed errors (exit 1 if exceeded)")
    parser.add_argument("--max-warnings", type=int, default=None, help="Max allowed warnings (exit 1 if exceeded)")

    # New: Auto-fix (#1)
    parser.add_argument("--fix", action="store_true", help="Apply auto-fixes")
    parser.add_argument("--dry-run", action="store_true", help="Show what --fix would change without writing")

    # New: Custom rules (#3)
    parser.add_argument("--custom-rules", type=Path, help="Directory with custom .yml rules (default: .ai-rules/)")

    # New: Health score (#10)
    parser.add_argument("--health-score", action="store_true", help="Show project health score")

    # New: Linter aggregation (#9)
    parser.add_argument(
        "--linters",
        nargs="*",
        choices=["ruff", "mypy", "eslint", "golangci-lint"],
        help="Run external linters and aggregate results",
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        return 1

    language = args.lang

    # Load custom rules
    custom_rules = None
    if args.custom_rules:
        custom_rules = load_custom_rules(args.custom_rules)
    elif args.auto_detect or args.path.is_dir():
        # Auto-detect .ai-rules in project root
        project_dir = args.path if args.path.is_dir() else args.path.parent
        custom_rules = load_custom_rules(project_dir)

    if args.path.is_file():
        if language is None:
            language = detect_language_from_file(args.path)
        if language is None:
            print(f"Error: Cannot detect language for {args.path}. Use --lang.", file=sys.stderr)
            return 1
        results = [validate_file(args.path, language, custom_rules=custom_rules)]
    else:
        if language is None and not args.auto_detect:
            print("Error: Use --lang or --auto-detect for directories.", file=sys.stderr)
            return 1
        results = validate_directory(args.path, language, args.exclude, custom_rules=custom_rules)

    # Auto-fix (#1)
    if args.fix or args.dry_run:
        all_fixes: list[FixResult] = []
        for result in results:
            fp = Path(result.file)
            fixes = apply_fixes(fp, result.issues, dry_run=args.dry_run)
            all_fixes.extend(fixes)

        if all_fixes:
            action = "Would fix" if args.dry_run else "Fixed"
            print(f"\n{action} {len(all_fixes)} issue(s):")
            for fix in all_fixes:
                print(f"  {fix.file}:{fix.line} [{fix.rule_id}]")
                print(f"    - {fix.original}")
                print(f"    + {fix.fixed}")

        if args.dry_run and not results:
            return 0

    # Health score (#10)
    if args.health_score:
        health = calculate_health_score(results)
        print(f"\n  Health Score: {health.score}/100 (Grade: {health.grade})")
        for detail in health.details:
            print(f"    - {detail}")

    # Linter aggregation (#9)
    if args.linters:
        linter_issues = run_linter_aggregation(args.path, args.linters)
        if linter_issues:
            print(f"\n  Linter Results ({len(linter_issues)} issues from {', '.join(args.linters)}):")
            for issue in linter_issues[:20]:
                print(f"    [{issue['linter']}] {issue['file']}:{issue['line']} {issue['message']}")
            if len(linter_issues) > 20:
                print(f"    ... and {len(linter_issues) - 20} more")

    # Output (#6)
    if args.format != "text" or args.json_output:
        fmt = "json" if args.json_output else args.format
        content = write_report(results, fmt, args.output)
        if content and not args.output:
            print(content)
    else:
        exit_code = print_results(results, use_json=False)

        # Check thresholds
        if args.max_errors is not None:
            total_errors = sum(r.error_count for r in results)
            if total_errors > args.max_errors:
                print(f"\nFAILED: {total_errors} errors exceeds max-errors={args.max_errors}")
                return 1

        if args.max_warnings is not None:
            total_warnings = sum(r.warning_count for r in results)
            if total_warnings > args.max_warnings:
                print(f"\nFAILED: {total_warnings} warnings exceeds max-warnings={args.max_warnings}")
                return 1

        if args.fail_on_warnings and any(r.warning_count > 0 for r in results):
            return 1

        return exit_code

    # For non-text formats, still check thresholds
    if args.max_errors is not None:
        total_errors = sum(r.error_count for r in results)
        if total_errors > args.max_errors:
            return 1
    if args.max_warnings is not None:
        total_warnings = sum(r.warning_count for r in results)
        if total_warnings > args.max_warnings:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
