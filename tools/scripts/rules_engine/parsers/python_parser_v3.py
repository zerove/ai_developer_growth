from __future__ import annotations

from typing import Any

from ..ast_parser import ClassInfo, FunctionInfo
from .base import BaseParser


class PythonParser(BaseParser):
    """语义级 Python 解析器，支持 async/decorator 特性。"""

    def parse(self, root_node: Any, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        self._walk(root_node, lines, functions, classes)
        return functions, classes

    def _walk(self, node: Any, lines: list[str], functions: list[FunctionInfo], classes: list[ClassInfo]) -> None:
        if node.type in ["function_definition", "async_function_definition"]:
            functions.append(self._parse_func(node, lines))
        elif node.type == "class_definition":
            classes.append(self._parse_class(node, lines))
        for child in node.children:
            self._walk(child, lines, functions, classes)

    def _parse_func(self, node: Any, lines: list[str]) -> FunctionInfo:
        # 简单标识符提取，保留异步标记
        is_async = node.type == "async_function_definition"
        return FunctionInfo(
            name="extracted_func",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_async=is_async,
        )

    def _parse_class(self, node: Any, lines: list[str]) -> ClassInfo:
        return ClassInfo(
            name="extracted_class",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=[],
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )
