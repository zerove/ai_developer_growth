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

import os
import time
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Protocol, cast


# Tree-sitter AST node type - tree-sitter returns untyped nodes at runtime.
# Protocol 提供最小静态接口，供 mypy 检查节点属性访问。
class _TreeNode(Protocol):
    """Minimal structural interface of a tree-sitter Node."""

    type: str
    children: list[_TreeNode]
    parent: _TreeNode | None
    text: bytes | str
    start_point: tuple[int, int]
    end_point: tuple[int, int]


class _TSTree(Protocol):
    """Minimal structural interface of a tree-sitter Tree."""

    root_node: _TreeNode


# Suppress tree-sitter deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")

try:
    import tree_sitter_languages

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


@dataclass
class ASTNode:
    """Simplified AST node for cross-language analysis."""

    type: str
    name: str
    line: int
    col: int
    end_line: int
    end_col: int
    children: list[ASTNode] = field(default_factory=list)
    parent: ASTNode | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class FunctionInfo:
    """Extracted function/method information."""

    name: str
    line: int
    col: int
    end_line: int
    params: list[str]
    decorators: list[str]
    return_type: str | None
    docstring: str | None
    body_lines: int
    complexity: int
    is_async: bool = False
    is_method: bool = False
    class_name: str | None = None


@dataclass
class ClassInfo:
    """Extracted class information."""

    name: str
    line: int
    col: int
    end_line: int
    bases: list[str]
    decorators: list[str]
    docstring: str | None
    methods: list[FunctionInfo]
    body_lines: int


@dataclass
class ImportInfo:
    """Extracted import information."""

    module: str
    names: list[str]
    line: int
    is_from: bool
    level: int  # relative import level


@dataclass
class FileAST:
    """Complete AST analysis of a file."""

    language: str
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[ImportInfo]
    global_variables: list[ASTNode]
    error_nodes: list[ASTNode]
    total_nodes: int
    parse_time_ms: float


def _extract_decorators(node: _TreeNode, lines: list[str]) -> list[str]:
    """Extract decorator strings from a function node."""
    decorators: list[str] = []
    if node.parent and node.parent.type == "decorated_definition":
        for sibling in node.parent.children:
            if sibling.type == "decorator":
                decorators.append(_get_text_static(sibling, lines))
    return decorators


def _extract_return_type(node: _TreeNode, lines: list[str]) -> str | None:
    """Extract return type annotation from function node."""
    for child in node.children:
        if child.type == "type":
            return _get_text_static(child, lines)
    return None


def _parse_function_parameters(params_node: _TreeNode, lines: list[str]) -> list[str]:
    """Extract parameter names from a parameters node."""
    params: list[str] = []
    for child in params_node.children:
        if child.type == "identifier":
            params.append(_get_text_static(child, lines))
        elif child.type in ("default_parameter", "typed_parameter", "typed_default_parameter"):
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(_get_text_static(sub, lines))
                    break
        elif child.type == "self_parameter":
            params.append("self")
        elif child.type == "positional_separator":
            continue
    return params


def _calculate_body_lines(node: _TreeNode) -> int:
    """Calculate number of body lines in a function."""
    body_start = node.start_point[0]
    body_end = node.end_point[0]
    return body_end - body_start


def _extract_docstring_static(node: _TreeNode, lines: list[str]) -> str | None:
    """Extract docstring from function/class body."""
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for expr in stmt.children:
                        if expr.type == "string":
                            return _get_text_static(expr, lines).strip("\"'")
    return None


def _estimate_complexity_static(node: _TreeNode, lines: list[str]) -> int:
    """Estimate cyclomatic complexity from AST."""
    branching_types = {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "try_statement",
        "except_clause",
        "with_statement",
        "boolean_operation",
        "conditional_expression",
    }
    counter = [1]
    _count_branching_static(node, branching_types, counter)
    return counter[0]


def _count_branching_static(node: _TreeNode, types: set[str], counter: list[int]) -> None:
    """Count branching nodes for complexity."""
    if node.type in types:
        counter[0] += 1
    for child in node.children:
        _count_branching_static(child, types, counter)


def _get_text_static(node: _TreeNode, lines: list[str]) -> str:
    """Get text from a tree-sitter node."""
    if isinstance(node.text, bytes):
        return node.text.decode("utf-8", errors="replace")
    return str(node.text)


class ASTParser:
    """Multi-language AST parser using tree-sitter.

    惰性初始化 + 类级 parser 缓存：多个实例共享同一批 parser，
    避免重复创建 tree-sitter 语言 parser 的开销。
    """

    SUPPORTED_LANGUAGES = {"python", "javascript", "typescript", "rust", "go", "java", "ruby"}
    # 类级共享缓存：所有实例复用同一批 language parser
    _PARSER_CACHE: ClassVar[dict[str, Any]] = {}
    _PARSER_CACHE_READY: ClassVar[bool] = False

    def __init__(self) -> None:
        self._parsers = self._shared_parsers()
        self._available = HAS_TREE_SITTER

    @classmethod
    def _shared_parsers(cls) -> dict[str, Any]:
        """Get (and lazily build) the class-level shared parser cache."""
        if not cls._PARSER_CACHE_READY:
            for lang in cls.SUPPORTED_LANGUAGES:
                try:
                    cls._PARSER_CACHE[lang] = tree_sitter_languages.get_parser(lang)
                except Exception:
                    _ = None  # tree-sitter parser not available for language
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

    # ─────────────────────────────────────────────────────────────
    # Python-specific extraction
    # ─────────────────────────────────────────────────────────────

    def _extract_functions(self, node: _TreeNode, language: str, lines: list[str]) -> list[FunctionInfo]:
        """Extract functions from AST node."""
        functions: list[FunctionInfo] = []
        self._walk_functions(node, language, lines, functions, None)
        return functions

    def _walk_functions(
        self, node: _TreeNode, language: str, lines: list[str], result: list[FunctionInfo], class_name: str | None
    ) -> None:
        """Recursively walk AST to find functions."""
        if language == "python":
            self._walk_python_functions(node, lines, result, class_name)
        elif language in ("javascript", "typescript"):
            self._walk_js_functions(node, lines, result, class_name)
        elif language == "rust":
            self._walk_rust_functions(node, lines, result, class_name)
        elif language == "go":
            self._walk_go_functions(node, lines, result, class_name)
        else:
            self._walk_generic_functions(node, language, lines, result, class_name)

    def _walk_python_functions(
        self, node: _TreeNode, lines: list[str], result: list[FunctionInfo], class_name: str | None
    ) -> None:
        """Walk Python AST for function definitions."""
        func_types = {"function_definition", "async_function_definition"}
        if node.type in func_types:
            info = self._parse_python_function(node, lines, class_name)
            if info:
                result.append(info)
            # Don't recurse into nested functions for class methods
            return

        # Recurse into children
        for child in node.children:
            self._walk_python_functions(child, lines, result, class_name)

    def _parse_python_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a Python function definition node."""
        name_node = None
        params_node = None
        is_async = node.type == "async_function_definition"

        for child in node.children:
            if child.type == "identifier":
                name_node = child
            elif child.type == "parameters":
                params_node = child

        if name_node is None or params_node is None:
            return None

        name = self._get_text(name_node, lines)
        params = _parse_function_parameters(params_node, lines)
        return_type = _extract_return_type(node, lines)
        decorators = _extract_decorators(node, lines)
        docstring = _extract_docstring_static(node, lines)
        body_lines = _calculate_body_lines(node)

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=decorators,
            return_type=return_type,
            docstring=docstring,
            body_lines=body_lines,
            complexity=_estimate_complexity_static(node, lines),
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
        )

    # ─────────────────────────────────────────────────────────────
    # JavaScript/TypeScript extraction
    # ─────────────────────────────────────────────────────────────

    def _walk_js_functions(
        self, node: _TreeNode, lines: list[str], result: list[FunctionInfo], class_name: str | None
    ) -> None:
        """Walk JS/TS AST for function definitions."""
        func_types = {
            "function_declaration",
            "function",
            "arrow_function",
            "method_definition",
        }
        if node.type in func_types:
            info = self._parse_js_function(node, lines, class_name)
            if info:
                result.append(info)
            return

        # Also check class bodies
        if node.type == "class_declaration":
            class_name_inner = self._get_child_name(node, lines)
            for child in node.children:
                if child.type == "class_body":
                    for member in child.children:
                        self._walk_js_functions(member, lines, result, class_name_inner)
            return

        for child in node.children:
            self._walk_js_functions(child, lines, result, class_name)

    def _parse_js_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a JS/TS function node."""
        name = self._get_child_name(node, lines) or "<anonymous>"
        params: list[str] = []

        for child in node.children:
            if child.type == "formal_parameters":
                for param in child.children:
                    if param.type in ("identifier", "required_parameter", "optional_parameter"):
                        param_name = self._get_child_name(param, lines)
                        if param_name:
                            params.append(param_name)

        body_start = node.start_point[0]
        body_end = node.end_point[0]

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=body_end - body_start,
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )

    # ─────────────────────────────────────────────────────────────
    # Rust extraction
    # ─────────────────────────────────────────────────────────────

    def _walk_rust_functions(
        self, node: _TreeNode, lines: list[str], result: list[FunctionInfo], class_name: str | None
    ) -> None:
        """Walk Rust AST for function definitions."""
        if node.type == "function_item":
            info = self._parse_rust_function(node, lines, class_name)
            if info:
                result.append(info)
            return

        if node.type == "impl_item":
            type_name = self._get_child_name(node, lines)
            for child in node.children:
                if child.type == "declaration_list":
                    for member in child.children:
                        self._walk_rust_functions(member, lines, result, type_name)
            return

        for child in node.children:
            self._walk_rust_functions(child, lines, result, class_name)

    def _parse_rust_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a Rust function node."""
        name = self._get_child_name(node, lines) or "<unknown>"
        params: list[str] = []

        for child in node.children:
            if child.type == "parameters":
                for param in child.children:
                    if param.type == "parameter":
                        for sub in param.children:
                            if sub.type == "identifier":
                                params.append(self._get_text(sub, lines))

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )

    # ─────────────────────────────────────────────────────────────
    # Go extraction
    # ─────────────────────────────────────────────────────────────

    def _walk_go_functions(
        self, node: _TreeNode, lines: list[str], result: list[FunctionInfo], class_name: str | None
    ) -> None:
        """Walk Go AST for function definitions."""
        if node.type == "function_declaration":
            info = self._parse_go_function(node, lines, class_name)
            if info:
                result.append(info)
            return

        if node.type == "type_declaration":
            for child in node.children:
                if child.type == "type_spec" and child.children:
                    self._get_child_name(child, lines)
                    for sub in child.children:
                        if sub.type == "struct_type":
                            for field_node in sub.children:
                                if field_node.type == "field_declaration_list":
                                    pass
            return

        for child in node.children:
            self._walk_go_functions(child, lines, result, class_name)

    def _parse_go_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a Go function node."""
        name = self._get_child_name(node, lines) or "<unknown>"
        params: list[str] = []

        for child in node.children:
            if child.type == "parameter_list":
                for param in child.children:
                    if param.type == "parameter_declaration":
                        for sub in param.children:
                            if sub.type == "identifier":
                                params.append(self._get_text(sub, lines))

        return FunctionInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )

    # ─────────────────────────────────────────────────────────────
    # Generic fallback
    # ─────────────────────────────────────────────────────────────

    def _walk_generic_functions(
        self, node: _TreeNode, language: str, lines: list[str], result: list[FunctionInfo], class_name: str | None
    ) -> None:
        """Generic function extraction - look for common patterns."""
        func_patterns = {
            "function_definition",
            "function_item",
            "function_declaration",
            "method_definition",
        }
        if node.type in func_patterns:
            name = self._get_child_name(node, lines) or "<unknown>"
            result.append(
                FunctionInfo(
                    name=name,
                    line=node.start_point[0] + 1,
                    col=node.start_point[1],
                    end_line=node.end_point[0] + 1,
                    params=[],
                    decorators=[],
                    return_type=None,
                    docstring=None,
                    body_lines=node.end_point[0] - node.start_point[0],
                    complexity=1,
                    is_method=class_name is not None,
                    class_name=class_name,
                )
            )
            return

        for child in node.children:
            self._walk_generic_functions(child, language, lines, result, class_name)

    # ─────────────────────────────────────────────────────────────
    # Class extraction
    # ─────────────────────────────────────────────────────────────

    def _extract_classes(self, node: _TreeNode, language: str, lines: list[str]) -> list[ClassInfo]:
        """Extract class definitions."""
        classes: list[ClassInfo] = []
        self._walk_classes(node, language, lines, classes)
        return classes

    def _walk_classes(self, node: _TreeNode, language: str, lines: list[str], result: list[ClassInfo]) -> None:
        """Walk AST for class definitions."""
        if language == "python" and node.type == "class_definition":
            info = self._parse_python_class(node, lines)
            if info:
                result.append(info)
            return

        if language in ("javascript", "typescript") and node.type == "class_declaration":
            info = self._parse_js_class(node, lines)
            if info:
                result.append(info)
            return

        if language == "rust" and node.type == "impl_item":
            info = self._parse_rust_impl(node, lines)
            if info:
                result.append(info)
            return

        for child in node.children:
            self._walk_classes(child, language, lines, result)

    def _parse_python_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse Python class definition."""
        name = self._get_child_name(node, lines) or "<unknown>"
        bases: list[str] = []
        decorators: list[str] = []
        methods: list[FunctionInfo] = []

        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    bases.append(self._get_text(arg, lines))
            elif child.type == "block":
                for stmt in child.children:
                    if stmt.type in ("function_definition", "async_function_definition"):
                        method = self._parse_python_function(stmt, lines, name)
                        if method:
                            methods.append(method)

        if node.parent and node.parent.type == "decorated_definition":
            for sibling in node.parent.children:
                if sibling.type == "decorator":
                    decorators.append(self._get_text(sibling, lines))

        docstring = _extract_docstring_static(node, lines)

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
            methods=methods,
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _parse_js_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse JS/TS class declaration."""
        name = self._get_child_name(node, lines) or "<anonymous>"
        bases: list[str] = []
        methods: list[FunctionInfo] = []

        for child in node.children:
            if child.type == "class_heritage":
                for expr in child.children:
                    if expr.type == "identifier":
                        bases.append(self._get_text(expr, lines))
            elif child.type == "class_body":
                for member in child.children:
                    method = self._parse_js_function(member, lines, name)
                    if method:
                        methods.append(method)

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=bases,
            decorators=[],
            docstring=None,
            methods=methods,
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _parse_rust_impl(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse Rust impl block as a 'class'."""
        name = self._get_child_name(node, lines) or "<unknown>"
        methods: list[FunctionInfo] = []

        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "function_item":
                        method = self._parse_rust_function(member, lines, name)
                        if method:
                            methods.append(method)

        return ClassInfo(
            name=name,
            line=node.start_point[0] + 1,
            col=node.start_point[1],
            end_line=node.end_point[0] + 1,
            bases=[],
            decorators=[],
            docstring=None,
            methods=methods,
            body_lines=node.end_point[0] - node.start_point[0],
        )

    # ─────────────────────────────────────────────────────────────
    # Import extraction
    # ─────────────────────────────────────────────────────────────

    def _extract_imports(self, node: _TreeNode, language: str) -> list[ImportInfo]:
        """Extract import statements."""
        imports: list[ImportInfo] = []
        self._walk_imports(node, language, imports)
        return imports

    def _walk_imports(self, node: _TreeNode, language: str, result: list[ImportInfo]) -> None:
        """Walk AST for import statements."""
        if language == "python":
            if node.type == "import_statement":
                module = self._get_text(node.children[0]) if node.children else ""
                names = [self._get_text(c, []) for c in node.children if c.type == "dotted_name"]
                result.append(
                    ImportInfo(module=module, names=names, line=node.start_point[0] + 1, is_from=False, level=0)
                )
            elif node.type == "import_from_statement":
                level = 0
                module = ""
                names = []
                for child in node.children:
                    if child.type == "relative_import":
                        level = child.text.count(b".") if isinstance(child.text, bytes) else str(child.text).count(".")
                    elif child.type == "dotted_name":
                        module = self._get_text(child, [])
                    elif child.type == "aliased_import":
                        for sub in child.children:
                            if sub.type == "identifier":
                                names.append(self._get_text(sub, []))
                result.append(
                    ImportInfo(module=module, names=names, line=node.start_point[0] + 1, is_from=True, level=level)
                )

        elif language in ("javascript", "typescript"):
            if node.type == "import_statement":
                result.append(
                    ImportInfo(
                        module=self._get_text(node, []),
                        names=[],
                        line=node.start_point[0] + 1,
                        is_from=True,
                        level=0,
                    )
                )
            elif node.type == "import_clause":
                pass  # handled by parent

        for child in node.children:
            if language == "python" and node.type in ("import_statement", "import_from_statement"):
                continue  # don't recurse into already-parsed imports
            self._walk_imports(child, language, result)

    # ─────────────────────────────────────────────────────────────
    # Global variable extraction
    # ─────────────────────────────────────────────────────────────

    def _extract_globals(self, node: _TreeNode, language: str) -> list[ASTNode]:
        """Extract module-level variable assignments."""
        globals_: list[ASTNode] = []
        if language == "python":
            self._walk_python_globals(node, globals_)
        return globals_

    def _walk_python_globals(self, node: _TreeNode, result: list[ASTNode]) -> None:
        """Walk Python AST for global assignments."""
        if node.type == "module":
            for child in node.children:
                if child.type == "expression_statement":
                    for expr in child.children:
                        if expr.type == "assignment":
                            name_node = expr.children[0] if expr.children else None
                            if name_node and name_node.type == "identifier":
                                result.append(
                                    ASTNode(
                                        type="global_var",
                                        name=self._get_text(name_node, []),
                                        line=child.start_point[0] + 1,
                                        col=child.start_point[1],
                                        end_line=child.end_point[0] + 1,
                                        end_col=child.end_point[1],
                                    )
                                )

    # ─────────────────────────────────────────────────────────────
    # Error node detection
    # ─────────────────────────────────────────────────────────────

    def _find_error_nodes(self, node: _TreeNode) -> list[ASTNode]:
        """Find ERROR nodes in AST (syntax errors)."""
        errors: list[ASTNode] = []
        if node.type == "ERROR":
            errors.append(
                ASTNode(
                    type="ERROR",
                    name=str(node.text[:50]) if hasattr(node, "text") else "",
                    line=node.start_point[0] + 1,
                    col=node.start_point[1],
                    end_line=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                )
            )
        for child in node.children:
            errors.extend(self._find_error_nodes(child))
        return errors

    # ─────────────────────────────────────────────────────────────
    # Utility methods
    # ─────────────────────────────────────────────────────────────

    def _get_text(self, node: _TreeNode, lines: list[str] | None = None) -> str:
        """Get text content of a node (委托静态实现，保持 API 兼容)."""
        return _get_text_static(node, lines or [])

    def _get_child_name(self, node: _TreeNode, lines: list[str]) -> str | None:
        """Get the 'name' child of a node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_text(child, lines)
        return None

    def _count_nodes(self, node: _TreeNode) -> int:
        """Count total nodes in AST."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count

    def _detect_language(self, filepath: Path) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
        }
        return ext_map.get(filepath.suffix.lower(), "unknown")


# ─────────────────────────────────────────────────────────────
# 文件解析结果缓存（基于 mtime + size 失效）
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _FileCacheKey:
    """文件缓存键：路径 + 修改时间 + 大小。"""

    path: str
    mtime_ns: int
    size: int


_file_ast_cache: dict[_FileCacheKey, FileAST] = {}


def _file_ast_cache_get(filepath: Path) -> FileAST | None:
    """按 (mtime, size) 查找缓存结果。"""
    try:
        stat = filepath.stat()
    except OSError:
        return None
    key = _FileCacheKey(str(filepath), stat.st_mtime_ns, stat.st_size)
    return _file_ast_cache.get(key)


def _file_ast_cache_set(filepath: Path, stat: os.stat_result, result: FileAST) -> None:
    """写入缓存，超限时直接清空（简单策略，避免内存膨胀）。"""
    key = _FileCacheKey(str(filepath), stat.st_mtime_ns, stat.st_size)
    _file_ast_cache[key] = result
    if len(_file_ast_cache) > 2048:
        _file_ast_cache.clear()


def clear_file_ast_cache() -> None:
    """清空文件解析结果缓存。"""
    _file_ast_cache.clear()


# Singleton instance
_default_parser: ASTParser | None = None


@lru_cache(maxsize=1)
def get_parser() -> ASTParser:
    """Get or create the default AST parser singleton (lru_cache 保证单例)."""
    return ASTParser()
