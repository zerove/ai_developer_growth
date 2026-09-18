"""AST Walkers 基础类与通用工具。

包含 _ImportWalkers 基类及通用工具方法：
- import/globals/error 提取
- 语言检测
- 节点文本提取
- 迭代化 AST 遍历工具
"""

from __future__ import annotations

from pathlib import Path

from .._ast_utils import (
    _count_nodes,
    _get_text_static,
)
from ..ast_nodes import ASTNode, ImportInfo, _TreeNode


class _ImportWalkers:
    """import/globals/error 提取与通用工具私有方法。"""

    def _extract_imports(self, node: _TreeNode, language: str) -> list[ImportInfo]:
        """Extract import statements."""
        imports: list[ImportInfo] = []
        self._walk_imports(node, language, imports)
        return imports

    def _parse_python_import(self, node: _TreeNode) -> ImportInfo | None:
        """解析 Python import 语句."""
        if node.type == "import_statement":
            return self._parse_import_statement(node)
        if node.type == "import_from_statement":
            return self._parse_import_from_statement(node)
        return None

    def _parse_import_statement(self, node: _TreeNode) -> ImportInfo:
        """解析 import X (含 aliased)."""
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
        """解析 from X import Y (含 relative + aliased)."""
        level, dotted_names, names, relative_seen = self._extract_from_components(node)
        return self._assemble_from_import(
            dotted_names=dotted_names,
            names=names,
            relative_seen=relative_seen,
            level=level,
            line=node.start_point[0] + 1,
        )

    def _extract_from_components(self, node: _TreeNode) -> tuple[int, list[str], list[str], bool]:
        """从 from_statement 抽取 4 组件."""
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
        """组装 from_import ImportInfo."""
        if not dotted_names:
            return ImportInfo(module="", names=names, line=line, is_from=True, level=level)
        if relative_seen:
            return ImportInfo(module="", names=dotted_names + names, line=line, is_from=True, level=level)
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
        return None

    def _walk_imports(self, node: _TreeNode, language: str, result: list[ImportInfo]) -> None:
        """Walk AST for import statements (迭代化，避免 RecursionError)."""
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
        """Find ERROR nodes in AST (syntax errors) - 迭代化."""
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
        """Count total nodes in AST."""
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
