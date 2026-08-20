from __future__ import annotations

from abc import ABC, abstractmethod

from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo, _TreeNode


class BaseParser(ABC):
    @abstractmethod
    def parse(
        self, root_node: _TreeNode, lines: list[str]
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        pass
