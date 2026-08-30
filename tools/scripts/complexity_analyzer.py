"""Complexity and threshold analysis for language rules validation.

Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from .validate_language_rules import Issue


def _check_line_length(lines: list[str], filepath: str, language: str, max_line: int) -> list[Issue]:
    """Check line length threshold."""
    issues: list[Issue] = []
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
    return issues


def _check_file_length(lines: list[str], filepath: str, language: str, max_file: int) -> list[Issue]:
    """Check file length threshold."""
    issues: list[Issue] = []
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
    return issues


def _check_function_length(
    func_lines: list[tuple[str, int, int]],
    filepath: str,
    language: str,
    max_func: int,
    max_nest: int,
    lines: list[str],
) -> list[Issue]:
    """Check function length and nesting depth thresholds."""
    issues: list[Issue] = []
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


def check_thresholds(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check quantitative thresholds."""
    issues: list[Issue] = []
    thresholds = rules.get("thresholds", {})
    language = rules.get("language", "")

    max_line = thresholds.get("max_line_length", 120)
    max_file = thresholds.get("max_file_length", 500)
    max_func = thresholds.get("max_function_length", 50)
    max_nest = thresholds.get("max_nesting_depth", 4)

    issues.extend(_check_line_length(lines, filepath, language, max_line))
    issues.extend(_check_file_length(lines, filepath, language, max_file))

    func_lines = extract_function_lines(lines, language)
    issues.extend(_check_function_length(func_lines, filepath, language, max_func, max_nest, lines))

    return issues


def extract_function_lines(lines: list[str], language: str) -> list[tuple[str, int, int]]:
    """Extract function name, start line, end line (V2.21 P5-12 拆分: 抽 _extract_python_functions + _extract_regex_functions)."""
    if language == "python":
        return _extract_python_functions(lines)
    if language in ("typescript", "ts", "rust", "go"):
        return _extract_regex_functions(lines, language)
    return []


def _extract_python_functions(lines: list[str]) -> list[tuple[str, int, int]]:
    """从 Python AST 提取函数名+行号范围 (模块级 helper).

    Args:
        lines: 源码行列表

    Returns:
        (name, start, end) 元组列表
    """
    functions: list[tuple[str, int, int]] = []
    try:
        tree = ast.parse("\n".join(lines))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                start = node.lineno
                end = getattr(node, "end_lineno", start + 50)
                functions.append((node.name, start, end))
    except SyntaxError:
        pass
    return functions


def _extract_regex_functions(lines: list[str], language: str) -> list[tuple[str, int, int]]:
    """用正则从非 Python 源码提取函数名+估算行号 (模块级 helper).

    Args:
        lines: 源码行列表
        language: typescript/rust/go

    Returns:
        (name, start, end) 元组列表
    """
    patterns: dict[str, list[str]] = {
        "typescript": [
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
            r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(",
        ],
        "rust": [r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"],
        "go": [r"func\s+(?:\([^)]+\)\s+)?(\w+)"],
    }
    functions: list[tuple[str, int, int]] = []
    content = "\n".join(lines)
    for pattern in patterns.get(language, []):
        for match in re.finditer(pattern, content):
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
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _check_python_function(node, filepath, issues)

    return issues


def _check_python_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: str,
    issues: list[Issue],
) -> None:
    """Check a Python function node for quality issues.

    V2.21 P5-6 拆分: 抽 _add_issue 收口 8 字段 Issue 构造模式,
    5 个 _check_* helper 收口各类型检查 (return/param/length/args/complexity),
    主函数仅委托.
    """
    _check_return_type(node, filepath, issues)
    _check_param_types(node, filepath, issues)
    _check_node_function_length(node, filepath, issues)
    _check_argument_count(node, filepath, issues)
    _check_cyclomatic_complexity(node, filepath, issues)


def _add_issue(
    issues: list[Issue],
    rule_id: str,
    severity: str,
    category: str,
    file: str,
    line: int,
    message: str,
) -> None:
    """添加 Issue 到列表 (模块级 helper).

    Args:
        issues: 累积列表
        rule_id: 规则 ID
        severity: 严重度
        category: 类别
        file: 文件路径
        line: 行号
        message: 错误消息
    """
    issues.append(
        Issue(
            rule_id=rule_id,
            severity=severity,
            category=category,
            file=file,
            line=line,
            message=message,
        )
    )


def _check_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef, filepath: str, issues: list[Issue]) -> None:
    """检查公共函数是否缺少返回类型注解 (模块级 helper)."""
    if node.returns is not None or node.name.startswith("_"):
        return
    _add_issue(
        issues,
        rule_id="py-ast-no-return-type",
        severity="info",
        category="type_safety",
        file=filepath,
        line=node.lineno,
        message=f"Public function '{node.name}' lacks return type annotation",
    )


def _check_param_types(node: ast.FunctionDef | ast.AsyncFunctionDef, filepath: str, issues: list[Issue]) -> None:
    """检查参数是否缺少类型注解 (排除 self/cls, 模块级 helper)."""
    for arg in node.args.args:
        if arg.annotation is not None or arg.arg in ("self", "cls"):
            continue
        _add_issue(
            issues,
            rule_id="py-ast-no-param-type",
            severity="info",
            category="type_safety",
            file=filepath,
            line=node.lineno,
            message=f"Parameter '{arg.arg}' of '{node.name}' lacks type annotation",
        )


def _check_node_function_length(
    node: ast.FunctionDef | ast.AsyncFunctionDef, filepath: str, issues: list[Issue]
) -> None:
    """检查函数行数 (≤ 50, 模块级 helper)."""
    if not (hasattr(node, "end_lineno") and node.end_lineno):
        return
    length = node.end_lineno - node.lineno + 1
    if length <= 50:
        return
    _add_issue(
        issues,
        rule_id="py-ast-function-length",
        severity="warning",
        category="readability",
        file=filepath,
        line=node.lineno,
        message=f"Function '{node.name}' is {length} lines (max 50)",
    )


def _check_argument_count(node: ast.FunctionDef | ast.AsyncFunctionDef, filepath: str, issues: list[Issue]) -> None:
    """检查参数个数 (≤ 7, 排除 self/cls, 模块级 helper)."""
    args = node.args
    total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
    if args.args and args.args[0].arg in ("self", "cls"):
        total_args -= 1
    if total_args <= 7:
        return
    _add_issue(
        issues,
        rule_id="py-ast-function-args",
        severity="warning",
        category="readability",
        file=filepath,
        line=node.lineno,
        message=f"Function '{node.name}' has {total_args} arguments (max 7)",
    )


def _check_cyclomatic_complexity(
    node: ast.FunctionDef | ast.AsyncFunctionDef, filepath: str, issues: list[Issue]
) -> None:
    """检查圈复杂度 (≤ 10, 模块级 helper)."""
    complexity = calc_cyclomatic_complexity(node)
    if complexity < 10:
        return
    _add_issue(
        issues,
        rule_id="py-ast-complexity",
        severity="warning",
        category="readability",
        file=filepath,
        line=node.lineno,
        message=f"Function '{node.name}' has cyclomatic complexity {complexity} (max 10)",
    )


def calc_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity for an AST node."""
    complexity = 1

    for child in ast.walk(node):
        if isinstance(child, ast.If | ast.While | ast.For | ast.AsyncFor):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.With | ast.AsyncWith):
            complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1

    return complexity
