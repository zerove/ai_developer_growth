"""AST 节点数据类型（dataclass + Protocol）。

从 ast_parser.py 抽出。Adr-014 渐进拆：先抽数据层（最稳定、零行为差异），
再考虑拆提取器。调用方 import 仍走 ast_parser 重导出，零迁移成本。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


# Tree-sitter AST node type - tree-sitter returns untyped nodes at runtime.
# Protocol 提供最小静态接口，供 mypy 检查节点属性访问。
class _TreeNode(Protocol):
    """Minimal structural interface of a tree-sitter Node."""

    type: str
    children: list[_TreeNode]
    parent: _TreeNode | None
    text: bytes | str
    start_point: tuple[int, int]
    end_point: tuple[int, int]


class _TSTree(Protocol):
    """Minimal structural interface of a tree-sitter Tree."""

    root_node: _TreeNode


@dataclass
class ASTNode:
    """Simplified AST node for cross-language analysis."""

    type: str
    name: str
    line: int
    col: int
    end_line: int
    end_col: int
    children: list[ASTNode] = field(default_factory=list)
    parent: ASTNode | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class FunctionInfo:
    """Extracted function/method information."""

    name: str
    line: int
    col: int
    end_line: int
    params: list[str]
    decorators: list[str]
    return_type: str | None
    docstring: str | None
    body_lines: int
    complexity: int
    is_async: bool = False
    is_method: bool = False
    class_name: str | None = None


@dataclass
class ClassInfo:
    """Extracted class information."""

    name: str
    line: int
    col: int
    end_line: int
    bases: list[str]
    decorators: list[str]
    docstring: str | None
    methods: list[FunctionInfo]
    body_lines: int


@dataclass
class ImportInfo:
    """Extracted import information."""

    module: str
    names: list[str]
    line: int
    is_from: bool
    level: int  # relative import level


@dataclass
class FileAST:
    """Complete AST analysis of a file."""

    language: str
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[ImportInfo]
    global_variables: list[ASTNode]
    error_nodes: list[ASTNode]
    total_nodes: int
    parse_time_ms: float


__all__ = [
    "_TreeNode",
    "_TSTree",
    "ASTNode",
    "FunctionInfo",
    "ClassInfo",
    "ImportInfo",
    "FileAST",
]
