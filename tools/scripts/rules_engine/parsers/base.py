from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo


class BaseParser(ABC):
    @abstractmethod
    def parse(self, root_node: object, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        pass
