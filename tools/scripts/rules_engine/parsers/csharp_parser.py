"""C# 语言 tree-sitter 解析器：提取类、接口、结构体、记录与方法。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, node_text
from tools.scripts.rules_engine.ast_nodes import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class CSharpParser(BaseParser):
    """解析 C# 的 class/interface/struct/record 声明与方法定义。"""

    _TYPE_DECLARATIONS = (
        "class_declaration",
        "interface_declaration",
        "struct_declaration",
        "record_declaration",
    )

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
        if node.type in self._TYPE_DECLARATIONS:
            classes.append(self._parse_class(node, lines))
            self._walk_type_body(node, lines, functions)
            # 继续下钻以捕获嵌套类型
        elif node.type == "method_declaration":
            if id(node) not in self._handled_methods:
                functions.append(self._parse_method(node))
        for child in node.children:
            self._walk(child, lines, functions, classes)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode | None) -> str:
        return node_text(node)

    def _parse_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        name_node = self._node_text(self._child_by_type(node, "identifier"))
        bases: list[str] = []
        base_list = self._child_by_type(node, "base_list")
        if base_list:
            bases = [
                self._node_text(c)
                for c in base_list.children
                if c.type in ("identifier", "type_identifier", "generic_name")
            ]
        kind = node.type.replace("_declaration", "")
        return ClassInfo(
            name=name_node or f"extracted_{kind}",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _walk_type_body(self, node: _TreeNode, lines: list[str], functions: list[FunctionInfo]) -> None:
        body = None
        for child in node.children:
            if child.type in ("declaration_list", "class_body"):
                body = child
                break
        if not body:
            return
        class_name = self._node_text(self._child_by_type(node, "identifier")) or None
        for item in body.children:
            if item.type == "method_declaration":
                self._handled_methods.add(id(item))
                info = self._parse_method(item)
                info.is_method = True
                info.class_name = class_name
                functions.append(info)

    def _parse_method(self, node: _TreeNode) -> FunctionInfo:
        params_node = self._child_by_type(node, "parameter_list")
        params: list[str] = []
        if params_node:
            params = [self._node_text(c) for c in params_node.children if c.type == "parameter"]
        # method_declaration 含多个 identifier（返回类型 + 方法名）；
        # 方法名是 parameter_list 之前紧邻的那个 identifier
        name = "extracted_method"
        for child in node.children:
            if child.type == "identifier":
                name_candidate = self._node_text(child)
            elif child.type == "parameter_list":
                name = name_candidate or name
                break
        return FunctionInfo(
            name=name,
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
