from .base import BaseParser
from .go_parser import GoParser
from .java_parser import JavaParser
from .python_parser import PythonParser
from .rust_parser import RustParser
from .typescript_parser import TypeScriptParser

PARSER_REGISTRY: dict[str, BaseParser] = {
    "python": PythonParser(),
    "go": GoParser(),
    "rust": RustParser(),
    "java": JavaParser(),
    "typescript": TypeScriptParser(),
}


def get_parser(language: str) -> BaseParser:
    """获取语言解析器；未知语言回退到 python 解析器（注册表实例）。"""
    parser = PARSER_REGISTRY.get(language)
    return parser if parser is not None else PARSER_REGISTRY["python"]
