from .base import BaseParser
from .go_parser import GoParser
from .python_parser import PythonParser
from .rust_parser import RustParser

PARSER_REGISTRY: dict[str, BaseParser] = {
    "python": PythonParser(),
    "go": GoParser(),
    "rust": RustParser(),
}


def get_parser(language: str) -> BaseParser:
    return PARSER_REGISTRY.get(language, PythonParser())
