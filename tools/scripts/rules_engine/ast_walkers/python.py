"""Python 语言专用 AST Walkers."""

from __future__ import annotations

from typing import Any

from .._ast_utils import (
    _estimate_complexity_static,
)
from .base import _ImportWalkers


class _PythonFunctionWalkers(_ImportWalkers):
    """Python 函数提取私有方法."""

    def _extract_functions(self, node: Any, language: str, lines: list[str]) -> list[Any]:
        """Extract functions from AST node."""
        functions: list[Any] = []
        self._walk_python_functions(node, lines, functions, None)
        return functions

    def _walk_python_functions(
        self,
        node: Any,
        lines: list[str],
        result: list[Any],
        class_name: str | None,
    ) -> None:
        """Walk Python AST for function definitions (迭代化)."""
        func_types = {"function_definition", "async_function_definition"}
        stack: list[Any] = [node]
        while stack:
            current = stack.pop()
            if current.type in func_types:
                info = self._parse_python_function(current, lines, class_name)
                if info:
                    result.append(info)
                continue
            stack.extend(reversed(current.children))

    def _parse_python_function(self, node: Any, lines: list[str], class_name: str | None) -> Any | None:
        """Parse a Python function definition node."""
        from ._ast_utils import (
            _calculate_body_lines,
            _extract_decorators,
            _extract_docstring_static,
            _extract_return_type,
            _parse_function_parameters,
        )
        from .ast_nodes import FunctionInfo

        name_node = None
        params_node = None
        is_async = node.type == "async_function_definition"

        for child in node.children:
            if child.type == "identifier":
                name_node = child
            elif child.type == "parameters":
                params_node = child

        if name_node is None or params_node is None:
            return None

        name = self._get_text(name_node, lines)
        params = _parse_function_parameters(params_node, lines)
        return_type = _extract_return_type(node, lines)
        decorators = _extract_decorators(node, lines)
        docstring = _extract_docstring_static(node, lines)
        body_lines = _calculate_body_lines(node)

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=decorators,
            return_type=return_type,
            docstring=docstring,
            body_lines=body_lines,
            complexity=_estimate_complexity_static(node, lines),
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
        )


class _PythonClassWalkers(_PythonFunctionWalkers):
    """Python 类提取私有方法."""

    def _parse_python_class(self, node: Any, lines: list[str]) -> Any | None:
        """Parse Python class definition."""
        from ..ast_nodes import ClassInfo

        name = self._get_child_name(node, lines) or "<unknown>"
        bases = self._parse_class_bases(node, lines)
        decorators = self._parse_class_decorators(node, lines)
        methods = self._parse_class_methods(node, lines)
        docstring = self._extract_docstring_static(node, lines)

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
            methods=methods,
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _parse_class_bases(self, node: Any, lines: list[str]) -> list[str]:
        """提取 class 基类."""
        bases: list[str] = []
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    bases.append(self._get_text(arg, lines))
        return bases

    def _parse_class_methods(self, node: Any, lines: list[str]) -> list[Any]:
        """提取 class 方法."""

        methods: list[Any] = []
        for child in node.children:
            if child.type != "block":
                continue
            for stmt in child.children:
                if stmt.type in ("function_definition", "async_function_definition"):
                    method = self._parse_python_function(
                        stmt, lines, class_name=self._get_class_name_for_method(node, lines)
                    )
                    if method:
                        methods.append(method)
        return methods

    def _get_class_name_for_method(self, node: Any, lines: list[str]) -> str:
        """获取 class 名称 (用于方法父类名)."""
        return self._get_child_name(node, lines) or "<unknown>"

    def _parse_class_decorators(self, node: Any, lines: list[str]) -> list[str]:
        """提取 class 装饰器."""
        decorators: list[str] = []
        if node.parent and node.parent.type == "decorated_definition":
            for sibling in node.parent.children:
                if sibling.type == "decorator":
                    decorators.append(self._get_text(sibling, lines))
        return decorators

    def _extract_docstring_static(self, node: Any, lines: list[str]) -> str | None:
        """Extract docstring from node (delegates to _ast_utils)."""
        from ._ast_utils import _extract_docstring_static

        return _extract_docstring_static(node, lines)
