"""通用 fallback 语言 AST Walkers (当无专用解析器时使用)."""

from __future__ import annotations

from typing import Any

from .base import _ImportWalkers


class _GenericFunctionWalkers(_ImportWalkers):
    """通用函数提取私有方法 (fallback)."""

    def _walk_generic_functions(
        self,
        node: Any,
        language: str,
        lines: list[str],
        result: list[Any],
        class_name: str | None,
    ) -> None:
        """Generic function extraction (迭代化)."""
        func_patterns = {
            "function_definition",
            "function_item",
            "function_declaration",
            "method_definition",
        }
        stack: list[tuple[Any, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type in func_patterns:
                name = self._get_child_name(current, lines) or "<unknown>"
                from .ast_nodes import FunctionInfo

                result.append(
                    FunctionInfo(
                        name=name,
                        line=current.start_point[0] + 1,
                        col=current.start_point[1],
                        end_line=current.end_point[0] + 1,
                        params=[],
                        decorators=[],
                        return_type=None,
                        docstring=None,
                        body_lines=current.end_point[0] - current.start_point[0],
                        complexity=1,
                        is_method=cur_class is not None,
                        class_name=cur_class,
                    )
                )
                continue
            for child in current.children:
                stack.append((child, cur_class))


class _GenericClassWalkers(_ImportWalkers):
    """通用类提取私有方法 (fallback)."""

    pass
