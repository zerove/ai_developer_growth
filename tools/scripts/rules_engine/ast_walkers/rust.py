"""Rust 语言专用 AST Walkers."""

from __future__ import annotations

from ..ast_nodes import ClassInfo, FunctionInfo, _TreeNode
from .base import _ImportWalkers


class _RustFunctionWalkers(_ImportWalkers):
    """Rust 函数提取私有方法."""

    def _walk_rust_functions(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk Rust AST for function definitions (迭代化)."""
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type == "function_item":
                info = self._parse_rust_function(current, lines, cur_class)
                if info:
                    result.append(info)
                continue

            if current.type == "impl_item":
                type_name = self._get_child_name(current, lines)
                for child in current.children:
                    if child.type == "declaration_list":
                        for member in child.children:
                            stack.append((member, type_name))
                continue

            for child in current.children:
                stack.append((child, cur_class))

    def _parse_rust_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a Rust function node."""
        name = self._get_child_name(node, lines) or "<unknown>"
        params: list[str] = []

        for child in node.children:
            if child.type == "parameters":
                for param in child.children:
                    if param.type == "parameter":
                        for sub in param.children:
                            if sub.type == "identifier":
                                params.append(self._get_text(sub, lines))

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )


class _RustClassWalkers(_RustFunctionWalkers):
    """Rust 类/Impl 块提取私有方法."""

    def _parse_rust_impl(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse Rust impl block as a 'class'."""
        name = self._get_child_name(node, lines) or "<unknown>"
        methods: list[FunctionInfo] = []

        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "function_item":
                        method = self._parse_rust_function(member, lines, name)
                        if method:
                            methods.append(method)

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=[],
            decorators=[],
            docstring=None,
            methods=methods,
            body_lines=node.end_point[0] - node.start_point[0],
        )
