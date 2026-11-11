"""PHP 语言 tree-sitter 解析器：提取函数、类方法与类定义。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, find_first, node_text
from tools.scripts.rules_engine.ast_nodes import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class PhpParser(BaseParser):
    """解析 PHP 的 function 声明、类方法与 class 定义。"""

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        if root_node is not None:
            self._walk(root_node, lines, functions, classes, None)
        return functions, classes

    def _walk(
        self,
        node: _TreeNode,
        lines: list[str],
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        class_name: str | None,
    ) -> None:
        if node is None:
            return
        if node.type == "class_declaration":
            info = self._parse_class(node, lines)
            classes.append(info)
            inner_functions: list[FunctionInfo] = []
            self._walk_methods(node, lines, inner_functions, info.name)
            # 方法同时挂到 ClassInfo.methods
            info.methods = list(inner_functions)
            functions.extend(inner_functions)
            return  # 类内部由 _walk_methods 处理，避免重复遍历
        if node.type == "function_definition":
            functions.append(self._parse_function(node, lines, class_name))
        for child in node.children:
            if child is not None:
                self._walk(child, lines, functions, classes, class_name)

    def _walk_methods(
        self,
        node: _TreeNode,
        lines: list[str],
        functions: list[FunctionInfo],
        class_name: str,
    ) -> None:
        """遍历类体收集 method_declaration。"""
        if node is None:
            return
        if node.type == "method_declaration":
            functions.append(self._parse_method(node, lines, class_name))
            return  # 不再深入方法体（避免嵌套函数重复归属）
        for child in node.children:
            if child is not None:
                self._walk_methods(child, lines, functions, class_name)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode) -> str:
        return node_text(node)

    def _parse_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        name_node = self._child_by_type(node, "name")
        bases: list[str] = []
        base_clause = self._child_by_type(node, "base_clause")
        if base_clause:
            for child in base_clause.children:
                if child.type in ("name", "qualified_name"):
                    bases.append(self._node_text(child))
        interface_clause = self._child_by_type(node, "class_interface_clause")
        if interface_clause:
            for child in interface_clause.children:
                if child.type in ("name", "qualified_name"):
                    bases.append(self._node_text(child))
        return ClassInfo(
            name=self._node_text(name_node) if name_node else "extracted_class",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=self._leading_doc(node),
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _parse_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo:
        name_node = self._child_by_type(node, "name")
        params_node = self._child_by_type(node, "formal_parameters")
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_func",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=self._collect_params(params_node) if params_node else [],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )

    def _parse_method(self, node: _TreeNode, lines: list[str], class_name: str) -> FunctionInfo:
        info = self._parse_function(node, lines, class_name)
        info.is_method = True
        return info

    def _collect_params(self, params_node: _TreeNode) -> list[str]:
        params: list[str] = []
        for child in params_node.children:
            if child.type in (
                "simple_parameter",
                "property_promotion_parameter",
                "variadic_parameter",
            ):
                var = self._find_first(child, "variable_name")
                if var is not None:
                    params.append(self._node_text(var))
                else:
                    params.append(self._node_text(child))
        return params

    def _leading_doc(self, node: _TreeNode) -> str | None:
        prev = node.prev_sibling if hasattr(node, "prev_sibling") else None
        if prev is None or prev.type != "comment":
            return None
        text = self._node_text(prev)
        return text if text.startswith("/**") else None

    def _find_first(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return find_first(node, node_type)
