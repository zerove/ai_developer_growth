"""Swift 语言 tree-sitter 解析器：提取类、结构体、协议、扩展与函数。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, node_text
from tools.scripts.rules_engine.ast_nodes import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class SwiftParser(BaseParser):
    """解析 Swift 的 class/struct/protocol/extension 声明与函数。"""

    _TYPE_DECLARATIONS = (
        "class_declaration",
        "struct_declaration",
        "protocol_declaration",
        "extension_declaration",
    )

    def __init__(self) -> None:
        self._handled_functions: set[int] = set()

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        self._handled_functions.clear()
        self._walk(root_node, lines, functions, classes)
        return functions, classes

    def _walk(
        self,
        node: _TreeNode,
        lines: list[str],
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
    ) -> None:
        if node is None:
            return
        if node.type in self._TYPE_DECLARATIONS:
            classes.append(self._parse_class(node, lines))
            self._walk_type_body(node, functions)
        elif node.type == "function_declaration":
            if id(node) not in self._handled_functions:
                functions.append(self._parse_function(node))
        for child in node.children:
            self._walk(child, lines, functions, classes)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode | None) -> str:
        return node_text(node)

    def _parse_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        name_node = self._child_by_type(node, "type_identifier") or self._child_by_type(node, "simple_identifier")
        bases: list[str] = []
        inheritance = self._child_by_type(node, "inheritance_specifier") or self._child_by_type(
            node, "inheritance_clause"
        )
        # inheritance_specifier 可能是单个节点；inheritance_clause 则含多个
        candidates = [inheritance] if node.type == "inheritance_specifier" else list(node.children)
        for holder in candidates:
            if holder is None or holder.type not in ("inheritance_specifier", "inheritance_clause"):
                continue
            for ut in self._find_all(holder, "type_identifier", max_depth=3):
                bases.append(self._node_text(ut))
        kind = node.type.replace("_declaration", "")
        return ClassInfo(
            name=self._node_text(name_node) or f"extracted_{kind}",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _walk_type_body(self, node: _TreeNode, functions: list[FunctionInfo]) -> None:
        body = self._child_by_type(node, "class_body")
        if not body:
            return
        name_node = self._child_by_type(node, "type_identifier") or self._child_by_type(node, "simple_identifier")
        class_name = self._node_text(name_node) or None
        for item in body.children:
            if item.type == "function_declaration":
                self._handled_functions.add(id(item))
                info = self._parse_function(item)
                info.is_method = True
                info.class_name = class_name
                functions.append(info)

    def _parse_function(self, node: _TreeNode) -> FunctionInfo:
        params_node = self._child_by_type(node, "parameter")
        params: list[str] = []
        if params_node:
            # parameter 直接是子节点（swift grammar 中 function_declaration 下有多个 parameter）
            params = [self._node_text(c) for c in node.children if c.type == "parameter"]
            if not params:
                params = [self._node_text(params_node)]
        # 返回类型: function_declaration 的 type_annotation 子节点
        return_type: str | None = None
        ta = self._child_by_type(node, "type_annotation")
        if ta is not None:
            return_type = self._node_text(ta)
        return FunctionInfo(
            name=self._node_text(self._child_by_type(node, "simple_identifier")) or "extracted_function",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=params,
            decorators=[],
            return_type=return_type,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
        )

    def _find_all(self, node: _TreeNode | None, node_type: str, max_depth: int) -> list[_TreeNode]:
        found: list[_TreeNode] = []
        if node is None or max_depth <= 0:
            return found
        for child in node.children:
            if child.type == node_type:
                found.append(child)
            found.extend(self._find_all(child, node_type, max_depth - 1))
        return found
