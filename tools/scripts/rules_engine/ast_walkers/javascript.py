"""JavaScript/TypeScript 语言专用 AST Walkers."""

from __future__ import annotations

from ..ast_nodes import ClassInfo, FunctionInfo, _TreeNode
from .base import _ImportWalkers


class _JavaScriptFunctionWalkers(_ImportWalkers):
    """JavaScript/TypeScript 函数提取私有方法."""

    def _walk_js_functions(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk JS/TS AST for function definitions (迭代化)."""
        func_types = {
            "function_declaration",
            "function",
            "arrow_function",
            "method_definition",
        }
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type in func_types:
                info = self._parse_js_function(current, lines, cur_class)
                if info:
                    result.append(info)
                continue

            if current.type == "class_declaration":
                class_name_inner = self._get_child_name(current, lines)
                for child in current.children:
                    if child.type == "class_body":
                        for member in child.children:
                            stack.append((member, class_name_inner))
                continue

            for child in current.children:
                stack.append((child, cur_class))

    def _parse_js_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a JS/TS function node."""
        name = self._get_child_name(node, lines) or "<anonymous>"
        params: list[str] = []

        for child in node.children:
            if child.type == "formal_parameters":
                for param in child.children:
                    if param.type in (
                        "identifier",
                        "required_parameter",
                        "optional_parameter",
                    ):
                        param_name = self._get_child_name(param, lines)
                        if param_name:
                            params.append(param_name)

        body_start = node.start_point[0]
        body_end = node.end_point[0]

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=body_end - body_start,
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )


class _JavaScriptClassWalkers(_JavaScriptFunctionWalkers):
    """JavaScript/TypeScript 类提取私有方法."""

    def _parse_js_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse JS/TS class declaration."""
        name = self._get_child_name(node, lines) or "<anonymous>"
        bases: list[str] = []
        methods: list[FunctionInfo] = []

        for child in node.children:
            if child.type == "class_heritage":
                for expr in child.children:
                    if expr.type == "identifier":
                        bases.append(self._get_text(expr, lines))
            elif child.type == "class_body":
                for member in child.children:
                    method = self._parse_js_function(member, lines, name)
                    if method:
                        methods.append(method)

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=bases,
            decorators=[],
            docstring=None,
            methods=methods,
            body_lines=node.end_point[0] - node.start_point[0],
        )
