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
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _common import handle_error

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# ──────────────────────────────────────────────────────────
# Rule cache (#7)
# ──────────────────────────────────────────────────────────

_RULE_CACHE: dict[str, dict[str, Any]] = {}
_FILE_HASH_CACHE: dict[str, str] = {}


def _file_hash(filepath: Path) -> str:
    """Quick content hash for incremental checks."""
    try:
        content = filepath.read_bytes()
        return hashlib.md5(content).hexdigest()
    except OSError:
        return ""


def _rules_hash(language: str) -> str:
    """Hash of rule file for cache invalidation."""
    rule_path = (
        Path(__file__).parent.parent.parent
        / "ai-dev-framework"
        / "languages"
        / language
        / "rules.d"
        / "anti_patterns.yml"
    )
    if not rule_path.exists():
        return ""
    try:
        return hashlib.md5(rule_path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _load_cache(cache_file: Path) -> dict[str, str]:
    """Load file hash cache from disk."""
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache_file: Path, cache: dict[str, str]) -> None:
    """Save file hash cache to disk."""
    try:
        cache_file.write_text(json.dumps(cache))
    except OSError:
        pass


def _get_supported_files(dirpath: Path, exclude: list[str]) -> list[Path]:
    """Get all supported files in a directory."""
    exclude = exclude or ["node_modules", "target", "vendor", ".git", "__pycache__", ".venv"]
    files = []
    for fp in sorted(dirpath.rglob("*")):
        if not fp.is_file():
            continue
        if any(ex in fp.parts for ex in exclude):
            continue
        if detect_language_from_file(fp):
            files.append(fp)
    return files


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
    """Load YAML rules for a given language with caching (#7)."""
    # Check cache
    rh = _rules_hash(language)
    cache_key = f"{language}:{rh}"
    if cache_key in _RULE_CACHE:
        return _RULE_CACHE[cache_key]

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

    result = data if isinstance(data, dict) else {}

    # Load common cross-language rules (#6)
    common = _load_common_rules(framework_dir)
    if common:
        result = _merge_rules(result, common)

    # Cache the result
    _RULE_CACHE[cache_key] = result
    return result


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
    """Merge custom rules into base rules. Custom overrides by ID.

    Supports two modes:
    - Full replacement: custom rule with same ID replaces the entire base rule
    - Severity override: custom rule with severity_override only changes severity
    """
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

        # Process base patterns: replace or apply severity_override
        merged_patterns = []
        for p in base_patterns:
            match = next((cp for cp in overridden if cp["id"] == p["id"]), None)
            if match:
                if "severity_override" in match:
                    # Only override severity, keep rest of base rule
                    p = dict(p)
                    p["severity"] = match["severity_override"]
                    merged_patterns.append(p)
                else:
                    # Full replacement with custom rule
                    merged_patterns.append(match)
            else:
                merged_patterns.append(p)
        merged_patterns.extend(new_only)
        merged["anti_patterns"] = merged_patterns

    # Merge naming
    if custom.get("naming"):
        merged.setdefault("naming", {}).update(custom["naming"])

    # Merge thresholds
    if custom.get("thresholds"):
        merged.setdefault("thresholds", {}).update(custom["thresholds"])

    return merged


# ──────────────────────────────────────────────────────────
# Cross-language common rules (#6)
# ──────────────────────────────────────────────────────────


def _load_common_rules(framework_dir: Path) -> dict[str, Any]:
    """Load common cross-language rules from common/security.yml."""
    common_path = framework_dir / "common" / "security.yml"
    if not common_path.exists() or yaml is None:
        return {}

    try:
        with open(common_path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


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
# Naming convention checker - Delegated to naming_analyzer.py
# ──────────────────────────────────────────────────────────


def check_naming_conventions(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check naming conventions based on language rules."""
    from .naming_analyzer import check_naming_conventions as _check

    return _check(lines, rules, filepath)


def _extract_identifiers(line: str, kind: str, language: str) -> list[str]:
    """Extract identifiers from a line based on the kind and language."""
    from .naming_analyzer import extract_identifiers

    return extract_identifiers(line, kind, language)


# ──────────────────────────────────────────────────────────
# Threshold checker - Delegated to complexity_analyzer.py
# ──────────────────────────────────────────────────────────


def check_thresholds(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check quantitative thresholds."""
    from .complexity_analyzer import check_thresholds as _check

    return _check(lines, rules, filepath)


def _extract_function_lines(lines: list[str], language: str) -> list[tuple[str, int, int]]:
    """Extract function name, start line, end line."""
    from .complexity_analyzer import extract_function_lines

    return extract_function_lines(lines, language)


def _max_nesting_depth(lines: list[str], language: str = "") -> int:
    """Calculate maximum nesting depth from lines."""
    from .complexity_analyzer import max_nesting_depth

    return max_nesting_depth(lines, language)


def _max_python_indent_depth(lines: list[str]) -> int:
    """Calculate max nesting depth for Python using indentation."""
    from .complexity_analyzer import _max_python_indent_depth

    return _max_python_indent_depth(lines)


# ──────────────────────────────────────────────────────────
# Python AST checks - Delegated to complexity_analyzer.py
# ──────────────────────────────────────────────────────────


def check_python_ast(filepath: str, lines: list[str]) -> list[Issue]:
    """Python-specific AST-based checks."""
    from .complexity_analyzer import check_python_ast as _check

    return _check(filepath, lines)


def _check_python_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: str,
    issues: list[Issue],
) -> None:
    """Check a Python function node for quality issues."""
    from .complexity_analyzer import _check_python_function as _check

    _check(node, filepath, issues)


def _calc_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity for an AST node."""
    from .complexity_analyzer import calc_cyclomatic_complexity

    return calc_cyclomatic_complexity(node)


# ──────────────────────────────────────────────────────────
# Auto-fix engine (#1)
# ──────────────────────────────────────────────────────────


def apply_fixes(filepath: Path, issues: list[Issue], dry_run: bool = False) -> list[FixResult]:
    """Apply auto-fixes to a file based on issues with fix_replacement.

    Delegated to fix_applier.apply_fixes for modularity.
    """
    from .fix_applier import apply_fixes as _apply_fixes

    return _apply_fixes(filepath, issues, dry_run)


# ──────────────────────────────────────────────────────────
# Report generators (#6) - Delegated to report_generator.py
# ──────────────────────────────────────────────────────────


def generate_junit_xml(results: list[ValidationResult]) -> str:
    """Generate JUnit XML report. Delegated to report_generator."""
    from .report_generator import generate_junit_xml as _gen

    return _gen(results)


def _xml_escape(s: str) -> str:
    """Escape XML special characters."""
    from .report_generator import _xml_escape as _esc

    return _esc(s)


def generate_html_report(results: list[ValidationResult]) -> str:
    """Generate HTML report. Delegated to report_generator."""
    from .report_generator import generate_html_report as _gen

    return _gen(results)


def _html_escape(s: str) -> str:
    """Escape HTML special characters."""
    from .report_generator import _html_escape as _esc

    return _esc(s)


def generate_sarif(results: list[ValidationResult]) -> str:
    """Generate SARIF 2.1.0 report. Delegated to report_generator."""
    from .report_generator import generate_sarif as _gen

    return _gen(results)


def write_report(results: list[ValidationResult], format: str, output: Path | None = None) -> str | None:
    """Write report in specified format. Delegated to report_generator."""
    from .report_generator import write_report as _write

    return _write(results, format, output)


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
# Linter aggregation (#9) - Delegated to linter_runner.py
# ──────────────────────────────────────────────────────────


def run_linter_aggregation(
    dirpath: Path,
    linters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run external linters and aggregate results."""
    from .linter_runner import run_linter_aggregation as _run

    return _run(dirpath, linters)


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
        choices=["text", "json", "html", "junit", "sarif"],
        default="text",
        help="Output format (default: text). sarif = GitHub Code Scanning",
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

    # New: Performance (#7)
    parser.add_argument(
        "--incremental", action="store_true", help="Skip files unchanged since last check (uses .rule-cache)"
    )
    parser.add_argument(
        "--changed-files", nargs="*", type=Path, help="Only check these specific files (for incremental)"
    )

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

    if args.changed_files:
        # Incremental: only check specified files (#7)
        results = []
        for fp in args.changed_files:
            if not fp.exists():
                continue
            lang = language or detect_language_from_file(fp)
            if lang:
                results.append(validate_file(fp, lang, custom_rules=custom_rules))
    elif args.path.is_file():
        if language is None:
            language = detect_language_from_file(args.path)
        if language is None:
            print(f"Error: Cannot detect language for {args.path}. Use --lang.", file=sys.stderr)
            return 1

        # Incremental: skip unchanged files (#7)
        if args.incremental:
            fh = _file_hash(args.path)
            cache_file = args.path.parent / ".rule-cache"
            cache = _load_cache(cache_file)
            if cache.get(str(args.path)) == fh:
                return 0  # File unchanged
            cache[str(args.path)] = fh
            _save_cache(cache_file, cache)

        results = [validate_file(args.path, language, custom_rules=custom_rules)]
    else:
        if language is None and not args.auto_detect:
            print("Error: Use --lang or --auto-detect for directories.", file=sys.stderr)
            return 1

        # Incremental: skip unchanged files in directory (#7)
        if args.incremental:
            cache_file = args.path / ".rule-cache"
            cache = _load_cache(cache_file)
            all_files = _get_supported_files(args.path, args.exclude)
            changed = [f for f in all_files if _file_hash(f) != cache.get(str(f))]
            # Update cache
            for f in all_files:
                cache[str(f)] = _file_hash(f)
            _save_cache(cache_file, cache)
            results = []
            for fp in changed:
                lang = language or detect_language_from_file(fp)
                if lang:
                    results.append(validate_file(fp, lang, custom_rules=custom_rules))
            if not results:
                print("No changed files detected (incremental mode).")
                return 0
        else:
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
    try:
        sys.exit(main())
    except Exception as e:
        handle_error(e, script="validate_language_rules")
