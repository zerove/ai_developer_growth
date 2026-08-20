"""Core validation pipeline: detect language → load rules → validate → report.

Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import Issue, ValidationResult

# Rule cache
_RULE_CACHE: dict[str, dict[str, Any]] = {}

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


def check_anti_patterns(
    lines: list[str], rules: dict[str, Any], filepath: str
) -> list[Issue]:
    """Check code lines against regex anti-patterns."""
    issues: list[Issue] = []
    if Path(filepath).name in {
        "rule_editor.py",
        "fix_heuristics.py",
        "ai_quality_gate.py",
        "auto_fix.py",
    }:
        return issues
    anti_patterns = rules.get("anti_patterns", [])
    filename = Path(filepath).name

    for pattern_def in anti_patterns:
        # Skip rule if file is in exclude_files list
        exclude_files = pattern_def.get("exclude_files", [])
        if exclude_files and any(
            filename == ef or Path(filepath).match(ef) for ef in exclude_files
        ):
            continue

        regex = re.compile(pattern_def["pattern"])

        for line_num, line in enumerate(lines, 1):
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


def load_rules(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load YAML rules for a given language with caching."""

    # Check cache
    cache_key = f"{language}:{_rules_hash(language, framework_dir)}"
    if cache_key in _RULE_CACHE:
        return _RULE_CACHE[cache_key]

    try:
        import yaml
    except ImportError:
        import sys as _sys

        print("Warning: PyYAML not installed. Using embedded rules.", file=_sys.stderr)
        return _get_embedded_rules(language)

    if framework_dir is None:
        framework_dir = Path(__file__).parent.parent.parent.parent / "ai-dev-framework"

    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    if not rule_path.exists():
        import sys as _sys

        print(
            f"Warning: Rules not found at {rule_path}, using embedded rules.",
            file=_sys.stderr,
        )
        return _get_embedded_rules(language)

    with open(rule_path) as f:
        data = yaml.safe_load(f)

    result = data if isinstance(data, dict) else {}

    # Load common cross-language rules
    common = _load_common_rules(framework_dir)
    if common:
        result = _merge_rules(result, common)

    # Cache the result
    _RULE_CACHE[cache_key] = result
    return result


def _rules_hash(language: str, framework_dir: Path | None = None) -> str:
    """Hash of rule file for cache invalidation."""
    import hashlib

    if framework_dir is None:
        framework_dir = Path(__file__).parent.parent.parent.parent / "ai-dev-framework"
    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"
    if not rule_path.exists():
        return ""
    try:
        return hashlib.sha256(rule_path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _load_common_rules(framework_dir: Path) -> dict[str, Any]:
    """Load common cross-language rules from common/security.yml."""
    common_path = framework_dir / "common" / "security.yml"
    if not common_path.exists():
        return {}

    try:
        import yaml

        with open(common_path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_custom_rules(project_dir: Path) -> dict[str, Any]:
    """Load custom rules from .ai-rules/*.yml in the project directory."""
    custom: dict[str, Any] = {"anti_patterns": [], "naming": {}, "thresholds": {}}
    rules_dir = project_dir / ".ai-rules"

    if not rules_dir.is_dir():
        return custom

    try:
        import yaml
    except ImportError:
        import sys as _sys

        print("Warning: PyYAML not installed. Custom rules skipped.", file=_sys.stderr)
        return custom

    for rule_file in sorted(rules_dir.glob("*.yml")):
        try:
            with open(rule_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue

            new_patterns = data.get("anti_patterns", [])
            custom["anti_patterns"].extend(new_patterns)

            if "naming" in data:
                custom["naming"].update(data["naming"])

            if "thresholds" in data:
                custom["thresholds"].update(data["thresholds"])

        except Exception as e:
            import sys as _sys

            print(f"Warning: Failed to load {rule_file}: {e}", file=_sys.stderr)

    return custom


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


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules. Custom overrides by ID."""
    merged = dict(base)

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

        merged_patterns = []
        for p in base_patterns:
            match = next((cp for cp in overridden if cp["id"] == p["id"]), None)
            if match:
                if "severity_override" in match:
                    p = dict(p)
                    p["severity"] = match["severity_override"]
                    merged_patterns.append(p)
                else:
                    merged_patterns.append(match)
            else:
                merged_patterns.append(p)
        merged_patterns.extend(new_only)
        merged["anti_patterns"] = merged_patterns

    if custom.get("naming"):
        merged.setdefault("naming", {}).update(custom["naming"])

    if custom.get("thresholds"):
        merged.setdefault("thresholds", {}).update(custom["thresholds"])

    return merged


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

    if custom_rules and (
        custom_rules.get("anti_patterns") or custom_rules.get("thresholds")
    ):
        rules = _merge_rules(rules, custom_rules)

    # 1. Regex anti-pattern checks
    from tools.scripts.complexity_analyzer import check_thresholds
    from tools.scripts.naming_analyzer import check_naming_conventions

    anti_issues = check_anti_patterns(lines, rules, str(filepath))
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
        from tools.scripts.complexity_analyzer import check_python_ast

        result.issues.extend(check_python_ast(str(filepath), lines))

    return result


def validate_directory(
    dirpath: Path,
    language: str | None = None,
    exclude: list[str] | None = None,
    custom_rules: dict[str, Any] | None = None,
) -> list[ValidationResult]:
    """Validate all supported files in a directory."""
    results: list[ValidationResult] = []
    exclude = exclude or [
        "node_modules",
        "target",
        "vendor",
        ".git",
        "__pycache__",
        ".venv",
    ]

    for filepath in sorted(dirpath.rglob("*")):
        if not filepath.is_file():
            continue

        if any(ex in filepath.parts for ex in exclude):
            continue

        file_lang = language or detect_language_from_file(filepath)
        if file_lang is None:
            continue

        results.append(validate_file(filepath, file_lang, custom_rules=custom_rules))

    return results
