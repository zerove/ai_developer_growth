from typing import Any

from ..ast_parser import ClassInfo, FunctionInfo
from .base import BaseParser


class GoParser(BaseParser):
    def parse(self, root_node: Any, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        # Go 语言的 AST 逻辑接入点
        return [], []
