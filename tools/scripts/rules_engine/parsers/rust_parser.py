from ..ast_parser import ClassInfo, FunctionInfo
from .base import BaseParser


class RustParser(BaseParser):
    def parse(
        self, root_node: object, lines: list[str]
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        # Rust 语言的 AST 逻辑接入点
        return [], []
