"""Kotlin 语言 tree-sitter 解析器：提取类、对象、接口与函数。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, node_text
from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class KotlinParser(BaseParser):
    """解析 Kotlin 的 class/object/interface 声明与 function_declaration。"""

    _TYPE_DECLARATIONS = ("class_declaration", "object_declaration")

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
            self._walk_class_body(node, functions)
        elif node.type == "interface_declaration":  # kotlin: interface 也走 class_declaration? 兜底
            classes.append(self._parse_class(node, lines))
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
        name = self._node_text(self._child_by_type(node, "identifier"))
        kind = "object" if node.type == "object_declaration" else "class"
        bases: list[str] = []
        delegation = self._child_by_type(node, "delegation_specifiers")
        if delegation:
            for spec in delegation.children:
                for ut in self._find_all(spec, "user_type", max_depth=2):
                    idn = self._child_by_type(ut, "identifier")
                    if idn:
                        bases.append(self._node_text(idn))
        return ClassInfo(
            name=name or f"extracted_{kind}",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _walk_class_body(self, node: _TreeNode, functions: list[FunctionInfo]) -> None:
        body = self._child_by_type(node, "class_body")
        if not body:
            return
        class_name = self._node_text(self._child_by_type(node, "identifier")) or None
        for item in body.children:
            if item.type == "function_declaration":
                self._handled_functions.add(id(item))
                info = self._parse_function(item)
                info.is_method = True
                info.class_name = class_name
                functions.append(info)

    def _parse_function(self, node: _TreeNode) -> FunctionInfo:
        params_node = self._child_by_type(node, "function_value_parameters")
        params: list[str] = []
        if params_node:
            params = [self._node_text(c) for c in params_node.children if c.type == "parameter"]
        # Kotlin 返回类型在 user_type 节点（冒号后）
        return_type: str | None = None
        for child in node.children:
            if child.type == "user_type":
                return_type = self._node_text(child)
        return FunctionInfo(
            name=self._node_text(self._child_by_type(node, "identifier")) or "extracted_function",
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
