from .base import BaseParser
from .cpp_parser import CppParser
from .csharp_parser import CSharpParser
from .go_parser import GoParser
from .java_parser import JavaParser
from .kotlin_parser import KotlinParser
from .php_parser import PhpParser
from .python_parser import PythonParser
from .ruby_parser import RubyParser
from .rust_parser import RustParser
from .swift_parser import SwiftParser
from .typescript_parser import TypeScriptParser

PARSER_REGISTRY: dict[str, BaseParser] = {
    "python": PythonParser(),
    "go": GoParser(),
    "rust": RustParser(),
    "java": JavaParser(),
    "typescript": TypeScriptParser(),
    "csharp": CSharpParser(),
    "kotlin": KotlinParser(),
    "swift": SwiftParser(),
    "cpp": CppParser(),
    "php": PhpParser(),
    "ruby": RubyParser(),
}


def get_parser(language: str) -> BaseParser:
    """获取语言解析器；未知语言回退到 python 解析器（注册表实例）。"""
    parser = PARSER_REGISTRY.get(language)
    return parser if parser is not None else PARSER_REGISTRY["python"]


def get_registry_parser(language: str) -> BaseParser | None:
    """按语言取注册解析器；未注册返回 None（不回退，供调用方自行降级）。"""
    return PARSER_REGISTRY.get(language)
