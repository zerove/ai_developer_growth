from __future__ import annotations
from typing import Any, Tuple, List
from ..models import FunctionInfo, ClassInfo
from .base import BaseParser

class PythonParser(BaseParser, ParserProtocol):
    """Python 解析器实现。"""
    def parse(self, root_node: Any, lines: List[str]) -> Tuple[List[FunctionInfo], List[ClassInfo]]:
        # 逻辑恢复
        return [], []
