"""Complexity metrics checker (lines, functions, nesting)."""

from __future__ import annotations

import ast
import re
from typing import Any

from .models import Issue


def check_python_complexity(
    lines: list[str],
    rules: dict[str, Any],
    filepath: str,
) -> list[Issue]:
    """Check Python complexity metrics."""
    issues: list[Issue] = []
    thresholds = rules.get("thresholds", {})

    max_lines = thresholds.get("max_lines_per_function", 50)
    max_nesting = thresholds.get("max_nesting_depth", 4)
    max_params = thresholds.get("max_parameters", 5)

    try:
        source = "\n".join(lines)
        tree = ast.parse(source)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            func_lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0
            if func_lines > max_lines:
                issues.append(
                    Issue(
                        rule_id="python-too-many-lines",
                        severity="warning",
                        category="complexity",
                        file=filepath,
                        line=node.lineno,
                        message=f"Function '{node.name}' has {func_lines} lines (max {max_lines})",
                        fix_hint="Break into smaller functions",
                    )
                )

            # Count parameters
            num_params = len(node.args.args) + len(node.args.kwonlyargs)
            if node.args.vararg:
                num_params += 1
            if node.args.kwarg:
                num_params += 1
            if num_params > max_params:
                issues.append(
                    Issue(
                        rule_id="python-too-many-params",
                        severity="warning",
                        category="complexity",
                        file=filepath,
                        line=node.lineno,
                        message=f"Function '{node.name}' has {num_params} parameters (max {max_params})",
                        fix_hint="Use dataclass or dict for parameters",
                    )
                )

            # Check nesting depth
            max_depth = _max_nesting_depth(node)
            if max_depth > max_nesting:
                issues.append(
                    Issue(
                        rule_id="python-too-deep-nesting",
                        severity="warning",
                        category="complexity",
                        file=filepath,
                        line=node.lineno,
                        message=f"Function '{node.name}' has nesting depth {max_depth} (max {max_nesting})",
                        fix_hint="Extract nested logic into helper functions",
                    )
                )

        elif isinstance(node, ast.ClassDef):
            # Count methods
            methods = [n for n in node.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
            max_methods = thresholds.get("max_methods_per_class", 20)
            if len(methods) > max_methods:
                issues.append(
                    Issue(
                        rule_id="python-too-many-methods",
                        severity="warning",
                        category="complexity",
                        file=filepath,
                        line=node.lineno,
                        message=f"Class '{node.name}' has {len(methods)} methods (max {max_methods})",
                        fix_hint="Split into multiple classes or use composition",
                    )
                )

    return issues


def _max_nesting_depth(node: ast.AST) -> int:
    """Calculate maximum nesting depth in a function."""
    max_depth = 0

    def visit(n: ast.AST, depth: int) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(n):
            if isinstance(child, ast.If | ast.For | ast.While | ast.Try | ast.With | ast.AsyncWith):
                visit(child, depth + 1)
            else:
                visit(child, depth)

    visit(node, 0)
    return max_depth


def check_js_complexity(
    lines: list[str],
    rules: dict[str, Any],
    filepath: str,
) -> list[Issue]:
    """Check JavaScript/TypeScript complexity metrics (regex-based)."""
    issues: list[Issue] = []
    thresholds = rules.get("thresholds", {})
    max_lines = thresholds.get("max_lines_per_function", 50)
    _ = thresholds.get("max_nesting_depth", 4)  # max_nesting reserved for future use

    # Simple regex-based function detection for JS/TS
    func_pattern = re.compile(
        r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>))"
    )
    _ = re.compile(r"[{}()]")  # brace_pattern reserved for future use

    # This is a simplified check - for production use, consider using a proper parser
    current_func = None
    func_start = 0
    brace_count = 0
    in_function = False

    for line_num, line in enumerate(lines, 1):
        _ = line.strip()  # stripped reserved for future use

        # Detect function start
        if not in_function:
            match = func_pattern.search(line)
            if match:
                current_func = match.group(1) or match.group(2)
                func_start = line_num
                in_function = True
                brace_count = 0
                # Count opening braces in this line
                brace_count += line.count("{")
                brace_count -= line.count("}")
        else:
            brace_count += line.count("{")
            brace_count -= line.count("}")

            if brace_count <= 0:
                # Function ended
                func_lines = line_num - func_start + 1
                if func_lines > max_lines:
                    issues.append(
                        Issue(
                            rule_id="js-too-many-lines",
                            severity="warning",
                            category="complexity",
                            file=filepath,
                            line=func_start,
                            message=f"Function '{current_func}' has {func_lines} lines (max {max_lines})",
                            fix_hint="Break into smaller functions",
                        )
                    )
                in_function = False
                current_func = None

    return issues
