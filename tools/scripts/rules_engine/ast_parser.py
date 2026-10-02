"""Tree-sitter AST parser for semantic code analysis.

Provides high-level AST parsing for Python, TypeScript, Rust, Go, JavaScript.
Falls back to regex-based analysis when tree-sitter is unavailable.

Usage:
    from tools.scripts.rules_engine.ast_parser import ASTParser

    parser = ASTParser()
    tree = parser.parse("def foo(): pass", language="python")
    functions = parser.extract_functions(tree, "python")
"""

from __future__ import annotations

import importlib
import sys
import time
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, cast

from ._ast_utils import _file_ast_cache_get as _file_ast_cache_get
from ._ast_utils import _file_ast_cache_set as _file_ast_cache_set
from ._ast_utils import clear_file_ast_cache as clear_file_ast_cache
from ._ast_walkers import _ClassWalkers as _ClassWalkers
from ._ast_walkers import _FunctionWalkers as _FunctionWalkers
from ._ast_walkers import _ImportWalkers as _ImportWalkers

# ADR-014 渐进拆: 数据类已抽到 ast_nodes.py,这里只 re-export
from .ast_nodes import (
    ASTNode,
    ClassInfo,
    FileAST,
    FunctionInfo,
    ImportInfo,
    _TreeNode,
    _TSTree,
)

# 显式 re-export: parsers/ 子包等模块通过 ast_parser 间接 import 数据类
__all__ = [
    "ASTNode",
    "ClassInfo",
    "FileAST",
    "FunctionInfo",
    "ImportInfo",
    "_TSTree",
    "_TreeNode",
    "ASTParser",
    "get_parser",
    "clear_file_ast_cache",
]


# Suppress tree-sitter deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")

# Try to import tree-sitter and language packages (tree-sitter 0.26+ API)
# Use individual language packages instead of tree_sitter_languages
#
# 按语言**逐个**导入, 而不是 12 个包写在同一个 try 里。
# 旧的写法是全有全无: 只要缺任何一个语言包, 就 except ImportError ->
# HAS_TREE_SITTER=False, 于是 parse_file 对**所有**语言恒返回 None,
# AST 语义检查整体静默失效, 而调用方拿到 None 也不报错 (fail-open)。
# 典型触发方式: 只装 tree-sitter + tree-sitter-python (本项目的实际做法)。
try:
    from tree_sitter import Language, Parser

    HAS_TREE_SITTER = True
except ImportError:
    Language = Any  # type: ignore[assignment,misc]
    Parser = Any  # type: ignore[assignment,misc]
    HAS_TREE_SITTER = False

# 语言名 -> (模块名, 取 language 对象的工厂)。缺失的语言会被单独跳过,
# 只影响该语言, 不再连坐其他语言。
_LANGUAGE_MODULES: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "rust": ("tree_sitter_rust", "language"),
    "go": ("tree_sitter_go", "language"),
    "java": ("tree_sitter_java", "language"),
    "ruby": ("tree_sitter_ruby", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
    "csharp": ("tree_sitter_c_sharp", "language"),
    "kotlin": ("tree_sitter_kotlin", "language"),
    "php": ("tree_sitter_php", "language_php"),
    "swift": ("tree_sitter_swift", "language"),
}


class ASTParser(_ClassWalkers, _FunctionWalkers, _ImportWalkers):
    """Multi-language AST parser using tree-sitter.

    惰性初始化 + 类级 parser 缓存：多个实例共享同一批 parser，
    避免重复创建 tree-sitter 语言 parser 的开销。
    """

    SUPPORTED_LANGUAGES = {
        "python",
        "javascript",
        "typescript",
        "rust",
        "go",
        "java",
        "ruby",
        "cpp",
        "csharp",
        "kotlin",
        "php",
        "swift",
    }
    # 类级共享缓存：所有实例复用同一批 language parser
    _PARSER_CACHE: ClassVar[dict[str, Any]] = {}
    _PARSER_CACHE_READY: ClassVar[bool] = False

    def __init__(self) -> None:
        self._parsers = self._shared_parsers()
        self._available = HAS_TREE_SITTER

    @classmethod
    def _shared_parsers(cls) -> dict[str, Any]:
        """Get (and lazily build) the class-level shared parser cache.

        每个语言独立导入: 缺 tree_sitter_go 只会让 go 不可用, 不再
        连带 python/rust 等全部失效。不可用的语言在 stderr 上明确报告,
        避免"AST 检查静默不工作"这类难以察觉的失效。
        """
        if not cls._PARSER_CACHE_READY:
            if HAS_TREE_SITTER:
                missing: list[str] = []
                for lang in cls.SUPPORTED_LANGUAGES:
                    spec = _LANGUAGE_MODULES.get(lang)
                    if spec is None:
                        missing.append(lang)
                        continue
                    module_name, factory_name = spec
                    try:
                        mod = importlib.import_module(module_name)
                        lang_obj = Language(getattr(mod, factory_name)())
                        cls._PARSER_CACHE[lang] = Parser(lang_obj)
                    except Exception as exc:  # noqa: BLE001
                        # 单个语言不可用不应拖垮其他语言, 但必须留痕。
                        missing.append(f"{lang}({type(exc).__name__})")
                if missing:
                    print(
                        f"⚠️  以下语言的 tree-sitter 解析器不可用, AST 检查将跳过它们: {', '.join(missing)}",
                        file=sys.stderr,
                    )
            cls._PARSER_CACHE_READY = True
        return cls._PARSER_CACHE

    @classmethod
    def reset_parser_cache(cls) -> None:
        """清空类级 parser 缓存（测试或热重载时使用）。"""
        cls._PARSER_CACHE.clear()
        cls._PARSER_CACHE_READY = False

    @property
    def available(self) -> bool:
        """Check if tree-sitter is available."""
        return self._available

    def supported_languages(self) -> set[str]:
        """Return languages with available parsers."""
        return set(self._parsers.keys())

    def parse(self, code: str | bytes, language: str) -> _TSTree | None:
        """Parse code into AST.

        Args:
            code: Source code string or bytes.
            language: Programming language name.

        Returns:
            tree-sitter Tree object, or None if parsing fails.
        """
        if not self._available or language not in self._parsers:
            return None

        if isinstance(code, str):
            code = code.encode("utf-8")

        try:
            parser = self._parsers[language]
            return cast(_TSTree, parser.parse(code))
        except Exception:
            return None

    def parse_file(self, filepath: Path, language: str | None = None, use_cache: bool = False) -> FileAST | None:
        """Parse a file and extract structured information.

        Args:
            filepath: Path to the source file.
            language: Language name. Auto-detected if None.
            use_cache: 启用基于 (mtime, size) 的文件结果缓存，
                同一文件未变更时跳过重复解析。默认关闭以保持原语义。

        Returns:
            FileAST with extracted information, or None if parsing fails.
        """
        if language is None:
            language = self._detect_language(filepath)

        if language not in self._parsers:
            return None

        if use_cache:
            cached = _file_ast_cache_get(filepath)
            if cached is not None:
                return cached

        try:
            stat = filepath.stat()
        except OSError:
            return None
        try:
            code = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        result = self._build_code(code, language)

        if result is None:
            return None
        if use_cache:
            _file_ast_cache_set(filepath, stat, result)
        return result

    def _build_code(self, code: str, language: str) -> FileAST | None:
        """从源码字符串构建 FileAST（供 parse_file 与缓存复用）。

        Args:
            code: 源码内容。
            language: 文件语言（必须已在 parsers 中）。

        Returns:
            FileAST 或解析失败返回 None。
        """
        start = time.monotonic()
        tree = self.parse(code, language)
        parse_time = (time.monotonic() - start) * 1000

        if tree is None:
            return None

        lines = code.splitlines()
        return FileAST(
            language=language,
            functions=self._extract_functions(tree.root_node, language, lines),
            classes=self._extract_classes(tree.root_node, language, lines),
            imports=self._extract_imports(tree.root_node, language),
            global_variables=self._extract_globals(tree.root_node, language),
            error_nodes=self._find_error_nodes(tree.root_node),
            total_nodes=self._count_nodes(tree.root_node),
            parse_time_ms=parse_time,
            total_lines=len(lines),  # Phase 33b-10 fix (ADR-051)
        )

    def extract_functions(self, tree: _TSTree, language: str, lines: list[str] | None = None) -> list[FunctionInfo]:
        """Extract function info from a parsed tree."""
        return self._extract_functions(tree.root_node, language, lines or [])

    def extract_classes(self, tree: _TSTree, language: str, lines: list[str] | None = None) -> list[ClassInfo]:
        """Extract class info from a parsed tree."""
        return self._extract_classes(tree.root_node, language, lines or [])

    def extract_imports(self, tree: _TSTree, language: str) -> list[ImportInfo]:
        """Extract import info from a parsed tree."""
        return self._extract_imports(tree.root_node, language)


# Singleton instance
_default_parser: ASTParser | None = None


@lru_cache(maxsize=1)
def get_parser() -> ASTParser:
    """Get or create the default AST parser singleton (lru_cache 保证单例)."""
    return ASTParser()
