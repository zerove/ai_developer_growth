"""Java 语言 tree-sitter 解析器：提取类、方法与字段。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, node_text
from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class JavaParser(BaseParser):
    """解析 Java 的 class/interface 声明与方法定义。"""

    def __init__(self) -> None:
        self._handled_methods: set[int] = set()

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        self._handled_methods.clear()
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
        if node.type == "class_declaration":
            classes.append(self._parse_class(node, lines))
            self._walk_class_body(node, lines, functions)
            return
        elif node.type in ("interface_declaration", "enum_declaration"):
            classes.append(self._parse_type_decl(node, lines))
        elif node.type == "method_declaration":
            if id(node) not in self._handled_methods:
                functions.append(self._parse_method(node, lines))
        for child in node.children:
            self._walk(child, lines, functions, classes)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode) -> str:
        return node_text(node)

    def _parse_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        name_node = self._child_by_type(node, "identifier")
        bases = [self._node_text(t) for t in self._find_all(node, "type_identifier", max_depth=4)]
        return ClassInfo(
            name=self._node_text(name_node) if name_node else "extracted_class",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _parse_type_decl(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        name_node = self._child_by_type(node, "identifier")
        kind = "interface" if node.type == "interface_declaration" else "enum"
        return ClassInfo(
            name=self._node_text(name_node) if name_node else f"extracted_{kind}",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=[],
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _walk_class_body(self, node: _TreeNode, lines: list[str], functions: list[FunctionInfo]) -> None:
        body = self._child_by_type(node, "class_body")
        if not body:
            return
        class_name_node = self._child_by_type(node, "identifier")
        class_name = self._node_text(class_name_node) if class_name_node else None
        for item in body.children:
            if item.type == "method_declaration":
                self._handled_methods.add(id(item))
                info = self._parse_method(item, lines)
                info.is_method = True
                info.class_name = class_name
                functions.append(info)

    def _parse_method(self, node: _TreeNode, lines: list[str]) -> FunctionInfo:
        name_node = self._child_by_type(node, "identifier")
        params_node = self._child_by_type(node, "formal_parameters")
        params = []
        if params_node:
            params = [self._node_text(c) for c in params_node.children if c.type == "formal_parameter"]
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_method",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
        )

    def _find_all(self, node: _TreeNode, node_type: str, max_depth: int) -> list[_TreeNode]:
        found: list[_TreeNode] = []
        if max_depth <= 0:
            return found
        for child in node.children:
            if child.type == node_type:
                found.append(child)
            found.extend(self._find_all(child, node_type, max_depth - 1))
        return found
