"""Go 语言专用 AST Walkers."""

from __future__ import annotations

from ..ast_nodes import ClassInfo, FunctionInfo, _TreeNode
from .base import _ImportWalkers


class _GoFunctionWalkers(_ImportWalkers):
    """Go 函数提取私有方法."""

    def _walk_go_functions(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk Go AST for function definitions (迭代化)."""
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type == "function_declaration":
                self._handle_function_declaration(current, lines, result, cur_class)
                continue
            for child in current.children:
                stack.append((child, cur_class))

    def _handle_function_declaration(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """处理 function_declaration 节点."""
        info = self._parse_go_function(node, lines, class_name)
        if info:
            result.append(info)

    def _parse_go_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a Go function node."""
        name = self._get_child_name(node, lines) or "<unknown>"
        params: list[str] = []

        for child in node.children:
            if child.type == "parameter_list":
                for param in child.children:
                    if param.type == "parameter_declaration":
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


class _GoClassWalkers(_ImportWalkers):
    """Go 类/Struct 提取私有方法."""

    def _parse_go_struct(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse Go type_declaration containing a struct_type as a ClassInfo."""
        name = self._get_child_name(node, lines) or "<unknown>"
        has_struct = False
        for child in node.children:
            if child.type == "type_spec":
                for sub in child.children:
                    if sub.type == "struct_type":
                        has_struct = True

        if not has_struct:
            return None

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=[],
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )
