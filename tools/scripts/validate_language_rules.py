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


def check_anti_patterns(
    lines: list[str], rules: dict[str, Any], filepath: str
) -> list[Issue]:
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
                issues.append(Issue(
                    rule_id=pattern_def["id"],
                    severity=pattern_def.get("severity", "warning"),
                    category=pattern_def.get("category", "general"),
                    file=filepath,
                    line=line_num,
                    column=match.start(),
                    message=pattern_def.get("message", "Anti-pattern detected"),
                    fix_hint=pattern_def.get("fix_hint", ""),
                ))

    return issues


# ──────────────────────────────────────────────────────────
# Naming convention checker
# ──────────────────────────────────────────────────────────


def check_naming_conventions(
    lines: list[str], rules: dict[str, Any], filepath: str
) -> list[Issue]:
    """Check naming conventions based on language rules."""
    issues: list[Issue] = []
    naming = rules.get("naming", {})
    language = rules.get("language", "")

    # Check filename
    file_rule = naming.get("file", {})
    if file_rule and "pattern" in file_rule:
        filename = Path(filepath).name
        if not re.match(file_rule["pattern"], filename):
            issues.append(Issue(
                rule_id=f"{language[:2]}-naming-file",
                severity="warning",
                category="naming",
                file=filepath,
                line=0,
                message=file_rule.get("message", f"File name '{filename}' violates naming convention"),
            ))

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
                    issues.append(Issue(
                        rule_id=f"{language[:2]}-naming-{kind}",
                        severity="info",
                        category="naming",
                        file=filepath,
                        line=line_num,
                        message=kind_rule.get("message", f"'{ident}' violates {kind} naming convention"),
                    ))

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
            m = re.match(r"(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:<[^>]+>\s+)?(\w+)\s+\w+\s*\(", line)
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
            m = re.match(r"(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:\w+\s+)?(\w+)\s*\(", line)
            if m and m.group(1) not in ("if", "for", "while", "switch", "catch", "try", "return", "new", "throw", "using"):
                identifiers.append(m.group(1))
        elif kind == "class":
            m = re.match(r"(?:public|private|protected|internal)?\s*(?:abstract\s+)?(?:sealed\s+)?(?:partial\s+)?class\s+(\w+)", line)
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

    return identifiers


# ──────────────────────────────────────────────────────────
# Threshold checker
# ──────────────────────────────────────────────────────────


def check_thresholds(
    lines: list[str], rules: dict[str, Any], filepath: str
) -> list[Issue]:
    """Check quantitative thresholds."""
    issues: list[Issue] = []
    thresholds = rules.get("thresholds", {})
    language = rules.get("language", "")

    # Line length
    max_line = thresholds.get("max_line_length", 120)
    for line_num, line in enumerate(lines, 1):
        if len(line.rstrip()) > max_line:
            issues.append(Issue(
                rule_id=f"{language[:2]}-threshold-line-length",
                severity="info",
                category="readability",
                file=filepath,
                line=line_num,
                message=f"Line length {len(line.rstrip())} exceeds {max_line}",
            ))

    # File length
    max_file = thresholds.get("max_file_length", 500)
    if len(lines) > max_file:
        issues.append(Issue(
            rule_id=f"{language[:2]}-threshold-file-length",
            severity="warning",
            category="readability",
            file=filepath,
            line=0,
            message=f"File has {len(lines)} lines (max {max_file})",
        ))

    # Function length and nesting depth
    max_func = thresholds.get("max_function_length", 50)
    max_nest = thresholds.get("max_nesting_depth", 4)

    func_lines = _extract_function_lines(lines, language)
    for func_name, start, end in func_lines:
        length = end - start + 1
        if length > max_func:
            issues.append(Issue(
                rule_id=f"{language[:2]}-threshold-func-length",
                severity="warning",
                category="readability",
                file=filepath,
                line=start,
                message=f"Function '{func_name}' is {length} lines (max {max_func})",
            ))

        # Check nesting depth within function
        depth = _max_nesting_depth(lines[start - 1:end], language)
        if depth > max_nest:
            issues.append(Issue(
                rule_id=f"{language[:2]}-threshold-nesting",
                severity="warning",
                category="readability",
                file=filepath,
                line=start,
                message=f"Function '{func_name}' has nesting depth {depth} (max {max_nest})",
            ))

    return issues


def _extract_function_lines(
    lines: list[str], language: str
) -> list[tuple[str, int, int]]:
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
                start = "\n".join(lines[:match.start()]).count("\n") + 1
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
        issues.append(Issue(
            rule_id="py-ast-syntax-error",
            severity="error",
            category="syntax",
            file=filepath,
            line=e.lineno or 1,
            message=f"Syntax error: {e.msg}",
        ))
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
        issues.append(Issue(
            rule_id="py-ast-no-return-type",
            severity="info",
            category="type_safety",
            file=filepath,
            line=node.lineno,
            message=f"Public function '{name}' lacks return type annotation",
        ))

    # Check parameter type annotations
    for arg in node.args.args:
        if arg.annotation is None and arg.arg != "self" and arg.arg != "cls":
            issues.append(Issue(
                rule_id="py-ast-no-param-type",
                severity="info",
                category="type_safety",
                file=filepath,
                line=node.lineno,
                message=f"Parameter '{arg.arg}' of '{name}' lacks type annotation",
            ))

    # Check function length
    if hasattr(node, "end_lineno") and node.end_lineno:
        length = node.end_lineno - node.lineno + 1
        if length > 50:
            issues.append(Issue(
                rule_id="py-ast-function-length",
                severity="warning",
                category="readability",
                file=filepath,
                line=node.lineno,
                message=f"Function '{name}' is {length} lines (max 50)",
            ))

    # Check argument count
    args = node.args
    total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
    # Subtract 'self' and 'cls'
    if args.args and args.args[0].arg in ("self", "cls"):
        total_args -= 1
    if total_args > 7:
        issues.append(Issue(
            rule_id="py-ast-function-args",
            severity="warning",
            category="readability",
            file=filepath,
            line=node.lineno,
            message=f"Function '{name}' has {total_args} arguments (max 7)",
        ))

    # Check cyclomatic complexity
    complexity = _calc_cyclomatic_complexity(node)
    if complexity >= 10:
        issues.append(Issue(
            rule_id="py-ast-complexity",
            severity="warning",
            category="readability",
            file=filepath,
            line=node.lineno,
            message=f"Function '{name}' has cyclomatic complexity {complexity} (max 10)",
        ))


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
# Main validation
# ──────────────────────────────────────────────────────────


def validate_file(filepath: Path, language: str) -> ValidationResult:
    """Validate a single file against language rules."""
    result = ValidationResult(file=str(filepath), language=language)

    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        result.issues.append(Issue(
            rule_id="read-error",
            severity="error",
            category="io",
            file=str(filepath),
            line=0,
            message=f"Cannot read file: {e}",
        ))
        return result

    result.lines_checked = len(lines)
    rules = load_rules(language)

    # 1. Regex anti-pattern checks
    result.issues.extend(check_anti_patterns(lines, rules, str(filepath)))

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
    ".js": "typescript",
    ".jsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
}


def detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


def validate_directory(
    dirpath: Path, language: str | None = None, exclude: list[str] | None = None
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

        results.append(validate_file(filepath, file_lang))

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
  %(prog)s lib/ --lang typescript --json
  %(prog)s . --auto-detect
  %(prog)s main.rs --lang rust
        """,
    )
    parser.add_argument("path", type=Path, help="File or directory to validate")
    parser.add_argument("--lang", choices=["python", "typescript", "rust", "go"],
                        help="Language to validate against")
    parser.add_argument("--auto-detect", action="store_true",
                        help="Auto-detect language from file extensions")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output results as JSON")
    parser.add_argument("--fail-on-warnings", action="store_true",
                        help="Exit with error on warnings")
    parser.add_argument("--exclude", nargs="*", default=["node_modules", "target", "vendor", ".git", "__pycache__", ".venv"],
                        help="Directories to exclude")

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        return 1

    language = args.lang

    if args.path.is_file():
        if language is None:
            language = detect_language_from_file(args.path)
        if language is None:
            print(f"Error: Cannot detect language for {args.path}. Use --lang.", file=sys.stderr)
            return 1
        results = [validate_file(args.path, language)]
    else:
        if language is None and not args.auto_detect:
            print("Error: Use --lang or --auto-detect for directories.", file=sys.stderr)
            return 1
        results = validate_directory(args.path, language, args.exclude)

    exit_code = print_results(results, use_json=args.json_output)

    if args.fail_on_warnings and any(r.warning_count > 0 for r in results):
        return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
