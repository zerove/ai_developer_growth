"""Complexity and threshold analysis for language rules validation.

Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from .validate_language_rules import Issue


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

    func_lines = extract_function_lines(lines, language)
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
        depth = max_nesting_depth(lines[start - 1 : end], language)
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


def extract_function_lines(lines: list[str], language: str) -> list[tuple[str, int, int]]:
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


def max_nesting_depth(lines: list[str], language: str = "") -> int:
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
    complexity = calc_cyclomatic_complexity(node)
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


def calc_cyclomatic_complexity(node: ast.AST) -> int:
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
