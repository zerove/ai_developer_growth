from typing import Protocol, runtime_checkable

from tools.scripts.rules_engine.ast_nodes import ClassInfo, FunctionInfo


@runtime_checkable
class ParserProtocol(Protocol):
    """AST 解析器的强制契约，确保所有解析器 API 一致。"""

    def parse(self, root_node: object, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]: ...


def validate_parser_contract(parser: ParserProtocol) -> bool:
    """验证解析器是否满足契约。"""
    try:
        assert hasattr(parser, "parse"), "解析器必须实现 parse 方法"
        return True
    except AssertionError:
        return False
