"""Rust 语言 tree-sitter 解析器：提取函数与 impl 块。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, find_first_at_depth, node_text
from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class RustParser(BaseParser):
    """解析 Rust 的 fn 定义、impl 块与 struct/enum/trait 定义。"""

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        if root_node is not None:
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
        if node.type == "function_item":
            functions.append(self._parse_func(node, lines))
        elif node.type in ("struct_item", "enum_item", "trait_item"):
            classes.append(self._parse_type(node, lines))
        elif node.type == "impl_item":
            # impl 块内的方法由 _walk_impl 统一提取，避免重复；
            # 仅跳过 declaration_list 的重复遍历，其余子节点正常递归
            self._walk_impl(node, lines, functions)
            for child in node.children:
                if child.type != "declaration_list":
                    self._walk(child, lines, functions, classes)
            return
        for child in node.children:
            self._walk(child, lines, functions, classes)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode) -> str:
        return node_text(node)

    def _walk_impl(self, node: _TreeNode, lines: list[str], functions: list[FunctionInfo]) -> None:
        type_node = self._find_first_at_depth(node, "type_identifier", 2)
        impl_name = self._node_text(type_node) if type_node else None
        for child in node.children:
            if child.type != "declaration_list":
                continue
            for item in child.children:
                if item.type == "function_item":
                    functions.append(self._parse_func(item, lines, class_name=impl_name))

    def _parse_func(self, node: _TreeNode, lines: list[str], class_name: str | None = None) -> FunctionInfo:
        name_node = self._child_by_type(node, "identifier")
        params_node = self._child_by_type(node, "parameters")
        is_async = any(c.type == "function_modifiers" for c in node.children)
        params = [self._node_text(c) for c in (params_node.children if params_node else []) if c.type == "parameter"]
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_fn",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
        )

    def _parse_type(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        name_node = self._child_by_type(node, "type_identifier")
        kind = "struct" if node.type == "struct_item" else ("trait" if node.type == "trait_item" else "enum")
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

    def _find_first_at_depth(self, node: _TreeNode, node_type: str, max_depth: int) -> _TreeNode | None:
        return find_first_at_depth(node, node_type, max_depth)
