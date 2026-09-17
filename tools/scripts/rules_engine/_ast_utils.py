"""ASTParser 内部工具函数与文件解析缓存（ADR-014 渐进拆）。

从 ast_parser.py 拆出的模块级静态辅助函数与基于 (mtime, size) 的文件缓存。
仅依赖 ast_nodes 数据层与标准库，不依赖 ast_parser facade。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .ast_nodes import FileAST, _TreeNode


def _extract_decorators(node: _TreeNode, lines: list[str]) -> list[str]:
    """Extract decorator strings from a function node."""
    decorators: list[str] = []
    if node.parent and node.parent.type == "decorated_definition":
        for sibling in node.parent.children:
            if sibling.type == "decorator":
                decorators.append(_get_text_static(sibling, lines))
    return decorators


def _extract_return_type(node: _TreeNode, lines: list[str]) -> str | None:
    """Extract return type annotation from function node."""
    for child in node.children:
        if child.type == "type":
            return _get_text_static(child, lines)
    return None


def _parse_function_parameters(params_node: _TreeNode, lines: list[str]) -> list[str]:
    """Extract parameter names from a parameters node."""
    params: list[str] = []
    for child in params_node.children:
        if child.type == "identifier":
            params.append(_get_text_static(child, lines))
        elif child.type in (
            "default_parameter",
            "typed_parameter",
            "typed_default_parameter",
        ):
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(_get_text_static(sub, lines))
                    break
        elif child.type == "self_parameter":
            params.append("self")
        elif child.type == "positional_separator":
            continue
    return params


def _calculate_body_lines(node: _TreeNode) -> int:
    """Calculate number of body lines in a function."""
    body_start = node.start_point[0]
    body_end = node.end_point[0]
    return body_end - body_start


def _extract_docstring_static(node: _TreeNode, lines: list[str]) -> str | None:
    """Extract docstring from function/class body."""
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for expr in stmt.children:
                        if expr.type == "string":
                            return _get_text_static(expr, lines).strip("\"'")
    return None


def _estimate_complexity_static(node: _TreeNode, lines: list[str]) -> int:
    """Estimate cyclomatic complexity from AST."""
    branching_types = {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "try_statement",
        "except_clause",
        "with_statement",
        "boolean_operation",
        "conditional_expression",
    }
    counter = [1]
    _count_branching_static(node, branching_types, counter)
    return counter[0]


def _count_branching_static(node: _TreeNode, types: set[str], counter: list[int]) -> None:
    """Count branching nodes for complexity (Phase 33b-7 fix, ADR-048: 迭代化).

    避免深度 binary_expression 或长 boolean_operation 链触发 RecursionError.
    """
    stack: list[_TreeNode] = [node]
    while stack:
        current = stack.pop()
        if current.type in types:
            counter[0] += 1
        stack.extend(current.children)


def _get_text_static(node: _TreeNode, lines: list[str]) -> str:
    """Get text from a tree-sitter node."""
    if isinstance(node.text, bytes):
        return node.text.decode("utf-8", errors="replace")
    return str(node.text)


# ─────────────────────────────────────────────────────────────
# 文件解析结果缓存（基于 mtime + size 失效）
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _FileCacheKey:
    """文件缓存键：路径 + 修改时间 + 大小。"""

    path: str
    mtime_ns: int
    size: int


_file_ast_cache: dict[_FileCacheKey, FileAST] = {}


def _file_ast_cache_get(filepath: Path) -> FileAST | None:
    """按 (mtime, size) 查找缓存结果。"""
    try:
        stat = filepath.stat()
    except OSError:
        return None
    key = _FileCacheKey(str(filepath), stat.st_mtime_ns, stat.st_size)
    return _file_ast_cache.get(key)


def _file_ast_cache_set(filepath: Path, stat: os.stat_result, result: FileAST) -> None:
    """写入缓存，超限时直接清空（简单策略，避免内存膨胀）。"""
    key = _FileCacheKey(str(filepath), stat.st_mtime_ns, stat.st_size)
    _file_ast_cache[key] = result
    if len(_file_ast_cache) > 2048:
        _file_ast_cache.clear()


def clear_file_ast_cache() -> None:
    """清空文件解析结果缓存。"""
    _file_ast_cache.clear()


def _count_nodes(node: _TreeNode) -> int:
    """Count total nodes in AST (Phase 33b-7 fix, ADR-048: 迭代化)."""
    count = 0
    stack: list[_TreeNode] = [node]
    while stack:
        current = stack.pop()
        count += 1
        stack.extend(current.children)
    return count
