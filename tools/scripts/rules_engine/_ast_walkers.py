"""ASTParser 私有 walk/parse 方法 mixin（ADR-014 渐进拆）。

从 ast_parser.py 拆出的按语言分组的私有方法，以 mixin 类形式提供。
依赖链: _ImportWalkers(基类, 含 import/globals/error/工具方法) ←
        _FunctionWalkers ← _ClassWalkers。
仅依赖 ast_nodes 数据层与 _ast_utils 工具函数，不依赖 ast_parser facade。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._ast_utils import (
    _calculate_body_lines,
    _count_nodes,
    _estimate_complexity_static,
    _extract_decorators,
    _extract_docstring_static,
    _extract_return_type,
    _get_text_static,
    _parse_function_parameters,
)
from .ast_nodes import ASTNode, ClassInfo, FunctionInfo, ImportInfo, _TreeNode


class _ImportWalkers:
    """import/globals/error 提取与通用工具私有方法。"""

    def _extract_imports(self, node: _TreeNode, language: str) -> list[ImportInfo]:
        """Extract import statements."""
        imports: list[ImportInfo] = []
        self._walk_imports(node, language, imports)
        return imports

    def _parse_python_import(self, node: _TreeNode) -> ImportInfo | None:
        """解析 Python import 语句 (V2.21 P5-43 拆分: 抽 _parse_import_statement + _parse_import_from_statement)."""
        if node.type == "import_statement":
            return self._parse_import_statement(node)
        if node.type == "import_from_statement":
            return self._parse_import_from_statement(node)
        return None

    def _parse_import_statement(self, node: _TreeNode) -> ImportInfo:
        """解析 import X (含 aliased) (模块级 helper, Phase 33b-5 fix).

        ADR-046: 原实现误取 children[0]='import' 关键字作 module.
        现收集首个 dotted_name 或 aliased_import 原始名为 module, 后续为 names.

        Args:
            node: import_statement 节点

        Returns:
            ImportInfo 实例
        """
        module = ""
        names: list[str] = []
        for child in node.children:
            if child.type == "dotted_name":
                name = self._get_text(child, [])
                if not module:
                    module = name
                else:
                    names.append(name)
            elif child.type == "aliased_import":
                # aliased_import 'a as b' -> 首个 identifier/dotted_name 是原始名
                # tree-sitter 中 'a' 是 dotted_name, 'b' 是 identifier
                for sub in child.children:
                    if sub.type in ("identifier", "dotted_name"):
                        name = self._get_text(sub, [])
                        if not module:
                            module = name
                        else:
                            names.append(name)
                        break
        return ImportInfo(module=module, names=names, line=node.start_point[0] + 1, is_from=False, level=0)

    def _parse_import_from_statement(self, node: _TreeNode) -> ImportInfo:
        """解析 from X import Y (含 relative + aliased) (Phase 33b-5 fix, ADR-046).

        委托 _extract_from_components 抽取 level/dotted_names/names/relative_seen,
        再由 _assemble_from_import 组装为 ImportInfo.
        """
        level, dotted_names, names, relative_seen = self._extract_from_components(node)
        return self._assemble_from_import(
            dotted_names=dotted_names,
            names=names,
            relative_seen=relative_seen,
            level=level,
            line=node.start_point[0] + 1,
        )

    def _extract_from_components(self, node: _TreeNode) -> tuple[int, list[str], list[str], bool]:
        """从 from_statement 抽取 4 组件 (模块级 helper, ADR-046)."""
        level = 0
        dotted_names: list[str] = []
        names: list[str] = []
        relative_seen = False
        for child in node.children:
            if child.type == "relative_import":
                level = child.text.count(b".") if isinstance(child.text, bytes) else str(child.text).count(".")
                relative_seen = True
            elif child.type == "dotted_name":
                dotted_names.append(self._get_text(child, []))
            elif child.type == "aliased_import":
                for sub in child.children:
                    if sub.type in ("identifier", "dotted_name"):
                        names.append(self._get_text(sub, []))
                        break
        return level, dotted_names, names, relative_seen

    def _assemble_from_import(
        self,
        dotted_names: list[str],
        names: list[str],
        relative_seen: bool,
        level: int,
        line: int,
    ) -> ImportInfo:
        """组装 from_import ImportInfo (模块级 helper, ADR-046)."""
        if not dotted_names:
            return ImportInfo(module="", names=names, line=line, is_from=True, level=level)
        if relative_seen:
            # relative: dotted_names 全是 names (relative_import 自带 ..pkg)
            return ImportInfo(module="", names=dotted_names + names, line=line, is_from=True, level=level)
        # from X import Y[, Z]: dotted_names[0]=X, 后续=Y, Z
        return ImportInfo(
            module=dotted_names[0],
            names=dotted_names[1:] + names,
            line=line,
            is_from=True,
            level=level,
        )

    def _parse_js_import(self, node: _TreeNode) -> ImportInfo | None:
        """解析 JavaScript/TypeScript import 语句。"""
        if node.type == "import_statement":
            return ImportInfo(
                module=self._get_text(node, []),
                names=[],
                line=node.start_point[0] + 1,
                is_from=True,
                level=0,
            )
        return None  # import_clause 由父节点处理

    def _walk_imports(self, node: _TreeNode, language: str, result: list[ImportInfo]) -> None:
        """Walk AST for import statements (Phase 33b-7 fix, ADR-048).

        迭代化: 用栈替代纯递归, 避免深度 binary_expression 触发 RecursionError.
        保持原 'already-parsed imports' 跳过逻辑 (不递归进入 import_statement 内部).
        """
        stack: list[_TreeNode] = [node]
        while stack:
            current = stack.pop()
            if language == "python":
                info = self._parse_python_import(current)
                if info:
                    result.append(info)
            elif language in ("javascript", "typescript"):
                info = self._parse_js_import(current)
                if info:
                    result.append(info)

            # already-parsed imports 不递归进入内部
            if language == "python" and current.type in (
                "import_statement",
                "import_from_statement",
            ):
                continue
            # 追加 children 到栈
            stack.extend(reversed(current.children))

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

    def _find_error_nodes(self, node: _TreeNode) -> list[ASTNode]:
        """Find ERROR nodes in AST (syntax errors).

        Phase 33b-7 fix (ADR-048): 迭代化避免深度 binary_expression 触发 RecursionError.
        """
        errors: list[ASTNode] = []
        stack: list[_TreeNode] = [node]
        while stack:
            current = stack.pop()
            if current.type == "ERROR":
                errors.append(
                    ASTNode(
                        type="ERROR",
                        name=str(current.text[:50]) if hasattr(current, "text") else "",
                        line=current.start_point[0] + 1,
                        col=current.start_point[1],
                        end_line=current.end_point[0] + 1,
                        end_col=current.end_point[1],
                    )
                )
            stack.extend(reversed(current.children))
        return errors

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
        """Count total nodes in AST (ADR-048 迭代化, 实现在 _ast_utils)."""
        return _count_nodes(node)

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
            ".cs": "csharp",
            ".kt": "kotlin",
            ".kts": "kotlin",
            ".swift": "swift",
            ".rb": "ruby",
            ".php": "php",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hh": "cpp",
            ".hxx": "cpp",
            ".c": "cpp",
            ".h": "cpp",
        }
        return ext_map.get(filepath.suffix.lower(), "unknown")


class _FunctionWalkers(_ImportWalkers):
    """函数提取相关私有方法（Python/JS/TS/Rust/Go/通用 fallback）。"""

    # 这些语言的提取委托给 parsers/registry 的专用解析器（含类方法归属、基类收集）
    _REGISTRY_DELEGATED_LANGUAGES = frozenset({"java", "csharp", "kotlin", "swift", "php", "ruby", "cpp"})

    def _registry_parse(self, tree_root: _TreeNode, language: str) -> tuple[list[FunctionInfo], list[ClassInfo]] | None:
        """尝试用 parsers/registry 专用解析器提取；语言未注册返回 None。"""
        try:
            from tools.scripts.rules_engine.parsers.registry import get_registry_parser

            reg = get_registry_parser(language)
            if reg is None:
                return None
            return reg.parse(tree_root, [])
        except Exception:
            return None

    def _extract_functions(self, node: _TreeNode, language: str, lines: list[str]) -> list[FunctionInfo]:
        """Extract functions from AST node."""
        if language in self._REGISTRY_DELEGATED_LANGUAGES:
            delegated = self._registry_parse(node, language)
            if delegated is not None:
                return delegated[0]
        functions: list[FunctionInfo] = []
        self._walk_functions(node, language, lines, functions, None)
        return functions

    def _walk_functions(
        self,
        node: _TreeNode,
        language: str,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
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
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk Python AST for function definitions (Phase 33b-7 fix, ADR-048).

        迭代化: 用栈替代纯递归, 避免深度 binary_expression (如 1+1+1+... * 1000)
        触发 RecursionError. 语义保持: 先访问父节点, 后访问子节点.
        """
        func_types = {"function_definition", "async_function_definition"}
        # 用列表作栈: [node_to_visit]
        # 单元素 stack 比 deque 简单, 不需要 maxlen
        stack: list[_TreeNode] = [node]
        while stack:
            current = stack.pop()
            if current.type in func_types:
                info = self._parse_python_function(current, lines, class_name)
                if info:
                    result.append(info)
                # Don't recurse into nested functions for class methods
                continue
            # 追加 children 到栈. 使用 reversed 让遍历顺序与原 for 一致 (depth-first)
            stack.extend(reversed(current.children))

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

    def _walk_js_functions(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk JS/TS AST for function definitions (Phase 33b-7 fix, ADR-048: 迭代化).

        栈元素: (node, class_name) - class 内部成员使用 inner class_name.
        """
        func_types = {
            "function_declaration",
            "function",
            "arrow_function",
            "method_definition",
        }
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type in func_types:
                info = self._parse_js_function(current, lines, cur_class)
                if info:
                    result.append(info)
                continue

            if current.type == "class_declaration":
                class_name_inner = self._get_child_name(current, lines)
                for child in current.children:
                    if child.type == "class_body":
                        # class_body 成员使用 inner class_name
                        for member in child.children:
                            stack.append((member, class_name_inner))
                continue

            # 默认: children 使用当前 class_name
            for child in current.children:
                stack.append((child, cur_class))

    def _parse_js_function(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo | None:
        """Parse a JS/TS function node."""
        name = self._get_child_name(node, lines) or "<anonymous>"
        params: list[str] = []

        for child in node.children:
            if child.type == "formal_parameters":
                for param in child.children:
                    if param.type in (
                        "identifier",
                        "required_parameter",
                        "optional_parameter",
                    ):
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

    def _walk_rust_functions(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk Rust AST for function definitions (Phase 33b-7 fix, ADR-048: 迭代化)."""
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type == "function_item":
                info = self._parse_rust_function(current, lines, cur_class)
                if info:
                    result.append(info)
                continue

            if current.type == "impl_item":
                type_name = self._get_child_name(current, lines)
                for child in current.children:
                    if child.type == "declaration_list":
                        for member in child.children:
                            stack.append((member, type_name))
                continue

            for child in current.children:
                stack.append((child, cur_class))

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

    def _walk_go_functions(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Walk Go AST for function definitions (Phase 33b-7 fix, ADR-048: 迭代化).

        V2.21 P5-44 拆分: 抽 _handle_function_declaration + _handle_type_declaration.
        """
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type == "function_declaration":
                self._handle_function_declaration(current, lines, result, cur_class)
                continue
            if current.type == "type_declaration":
                self._handle_type_declaration(current, lines, cur_class)
                continue
            for child in current.children:
                stack.append((child, cur_class))

    def _handle_function_declaration(
        self,
        node: _TreeNode,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """处理 function_declaration 节点 (方法级 helper, 内部 append result).

        Args:
            node: function_declaration 节点
            lines: 源码行
            result: 累积目标列表
            class_name: 类名
        """
        info = self._parse_go_function(node, lines, class_name)
        if info:
            result.append(info)

    def _handle_type_declaration(
        self,
        node: _TreeNode,
        lines: list[str],
        class_name: str | None,
    ) -> None:
        """处理 type_declaration 节点 (方法级 helper, 占位实现).

        当前仅识别 struct_type, 暂不构建方法列表.
        保留递归 + type_spec 遍历结构.

        Args:
            node: type_declaration 节点
            lines: 源码行
            class_name: 类名 (暂未使用, 占位)
        """
        for child in node.children:
            if child.type == "type_spec" and child.children:
                self._get_child_name(child, lines)
                for sub in child.children:
                    if sub.type == "struct_type":
                        for field_node in sub.children:
                            if field_node.type == "field_declaration_list":
                                pass

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

    def _walk_generic_functions(
        self,
        node: _TreeNode,
        language: str,
        lines: list[str],
        result: list[FunctionInfo],
        class_name: str | None,
    ) -> None:
        """Generic function extraction (Phase 33b-7 fix, ADR-048: 迭代化).

        Look for common patterns.
        """
        func_patterns = {
            "function_definition",
            "function_item",
            "function_declaration",
            "method_definition",
        }
        stack: list[tuple[_TreeNode, str | None]] = [(node, class_name)]
        while stack:
            current, cur_class = stack.pop()
            if current.type in func_patterns:
                name = self._get_child_name(current, lines) or "<unknown>"
                result.append(
                    FunctionInfo(
                        name=name,
                        line=current.start_point[0] + 1,
                        col=current.start_point[1],
                        end_line=current.end_point[0] + 1,
                        params=[],
                        decorators=[],
                        return_type=None,
                        docstring=None,
                        body_lines=current.end_point[0] - current.start_point[0],
                        complexity=1,
                        is_method=cur_class is not None,
                        class_name=cur_class,
                    )
                )
                continue
            for child in current.children:
                stack.append((child, cur_class))


class _ClassWalkers(_FunctionWalkers):
    """类提取相关私有方法。"""

    def _extract_classes(self, node: _TreeNode, language: str, lines: list[str]) -> list[ClassInfo]:
        """Extract class definitions."""
        if language in self._REGISTRY_DELEGATED_LANGUAGES:
            delegated = self._registry_parse(node, language)
            if delegated is not None:
                return delegated[1]
        classes: list[ClassInfo] = []
        self._walk_classes(node, language, lines, classes)
        return classes

    def _walk_classes(self, node: _TreeNode, language: str, lines: list[str], result: list[ClassInfo]) -> None:
        """Walk AST for class definitions (Phase 33b-7 fix, ADR-048).

        V2.21 P5-45 拆分: 抽 _dispatch_class_parse.
        迭代化 (33b-7): 用栈替代纯递归, 避免深度 binary_expression 触发 RecursionError.
        """
        stack: list[_TreeNode] = [node]
        while stack:
            current = stack.pop()
            handled = self._dispatch_class_parse(current, language, lines, result)
            if handled:
                continue
            # 追加 children 到栈 (reversed 保持原 depth-first 顺序)
            stack.extend(reversed(current.children))

    def _dispatch_class_parse(self, node: _TreeNode, language: str, lines: list[str], result: list[ClassInfo]) -> bool:
        """按 language 分派 class 解析 (模块级 helper).

        Args:
            node: AST 节点
            language: 目标语言
            lines: 源码行
            result: 累积目标列表

        Returns:
            True 表示已处理 (找到匹配), False 表示未匹配需继续递归
        """
        handlers: dict[tuple[str, str], Any] = {
            ("python", "class_definition"): lambda: self._parse_python_class(node, lines),
            ("javascript", "class_declaration"): lambda: self._parse_js_class(node, lines),
            ("typescript", "class_declaration"): lambda: self._parse_js_class(node, lines),
            ("rust", "impl_item"): lambda: self._parse_rust_impl(node, lines),
        }
        info = handlers.get((language, node.type))
        if info is None:
            return False
        parsed = info()
        if parsed:
            result.append(parsed)
        return True

    def _parse_python_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        """Parse Python class definition (V2.21 P5-42 拆分: 抽 _parse_class_bases + _parse_class_methods + _parse_class_decorators)."""
        name = self._get_child_name(node, lines) or "<unknown>"
        bases = self._parse_class_bases(node, lines)
        decorators = self._parse_class_decorators(node, lines)
        methods = self._parse_class_methods(node, lines)

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

    def _parse_class_bases(self, node: _TreeNode, lines: list[str]) -> list[str]:
        """提取 class 基类 (方法级 helper).

        Args:
            node: class 节点
            lines: 源码行

        Returns:
            基类名列表
        """
        bases: list[str] = []
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    bases.append(self._get_text(arg, lines))
        return bases

    def _parse_class_methods(self, node: _TreeNode, lines: list[str]) -> list[FunctionInfo]:
        """提取 class 方法 (方法级 helper).

        Args:
            node: class 节点
            lines: 源码行

        Returns:
            FunctionInfo 列表
        """
        methods: list[FunctionInfo] = []
        for child in node.children:
            if child.type != "block":
                continue
            for stmt in child.children:
                if stmt.type in ("function_definition", "async_function_definition"):
                    method = self._parse_python_function(
                        stmt, lines, class_name=self._get_class_name_for_method(node, lines)
                    )
                    if method:
                        methods.append(method)
        return methods

    def _get_class_name_for_method(self, node: _TreeNode, lines: list[str]) -> str:
        """获取 class 名称 (方法级 helper, 用于 _parse_python_function 父类名).

        Args:
            node: class 节点
            lines: 源码行

        Returns:
            class 名称
        """
        return self._get_child_name(node, lines) or "<unknown>"

    def _parse_class_decorators(self, node: _TreeNode, lines: list[str]) -> list[str]:
        """提取 class 装饰器 (方法级 helper).

        Args:
            node: class 节点
            lines: 源码行

        Returns:
            装饰器列表
        """
        decorators: list[str] = []
        if node.parent and node.parent.type == "decorated_definition":
            for sibling in node.parent.children:
                if sibling.type == "decorator":
                    decorators.append(self._get_text(sibling, lines))
        return decorators

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
