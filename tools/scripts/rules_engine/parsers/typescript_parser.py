"""TypeScript 语言 tree-sitter 解析器：提取类、方法与函数。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, find_first, node_text
from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class TypeScriptParser(BaseParser):
    """解析 TypeScript/TSX 的 class、method 与 function 声明。"""

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        self._walk(root_node, lines, functions, classes)
        return functions, classes

    def _walk(
        self,
        node: _TreeNode,
        lines: list[str],
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
    ) -> None:
        if node is None:
            return
        if node.type == "class_declaration":
            classes.append(self._parse_class(node, lines))
            self._walk_class_body(node, lines, functions)
        elif node.type == "function_declaration":
            functions.append(self._parse_function(node, lines))
        elif node.type in ("lexical_declaration", "variable_declaration"):
            info = self._parse_arrow_assign(node, lines)
            if info:
                functions.append(info)
        for child in node.children:
            self._walk(child, lines, functions, classes)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode) -> str:
        return node_text(node)

    def _parse_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        """Parse TS/JS class (V2.22 P6-9 拆分: 抽 _extract_ts_class_bases, 方法级 helper)."""
        name_node = self._find_first(node, "type_identifier") or self._find_first(node, "identifier")
        bases = self._extract_ts_class_bases(node)
        return ClassInfo(
            name=self._node_text(name_node) if name_node else "extracted_class",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _extract_ts_class_bases(self, node: _TreeNode) -> list[str]:
        """提取 TS/JS class 基类 (extends + implements, 方法级 helper).

        Args:
            node: class 节点

        Returns:
            基类名列表
        """
        bases: list[str] = []
        heritage = self._child_by_type(node, "class_heritage")
        if heritage is None:
            return bases
        for clause in heritage.children:
            if clause.type == "extends_clause":
                ident = self._find_first(clause, "identifier") or self._find_first(clause, "type_identifier")
                if ident:
                    bases.append(self._node_text(ident))
            elif clause.type == "implements_clause":
                bases.extend(self._node_text(t) for t in self._find_all(clause, "type_identifier"))
        return bases

    def _walk_class_body(self, node: _TreeNode, lines: list[str], functions: list[FunctionInfo]) -> None:
        body = self._child_by_type(node, "class_body")
        if not body:
            return
        name_node = self._find_first(node, "type_identifier") or self._find_first(node, "identifier")
        class_name = self._node_text(name_node) if name_node else None
        for item in body.children:
            if item.type == "method_definition":
                info = self._parse_method(item, lines)
                info.is_method = True
                info.class_name = class_name
                functions.append(info)

    def _parse_method(self, node: _TreeNode, lines: list[str]) -> FunctionInfo:
        name_node = self._child_by_type(node, "property_identifier")
        params_node = self._child_by_type(node, "formal_parameters")
        params = []
        if params_node:
            params = [
                self._node_text(c)
                for c in params_node.children
                if c.type in ("required_parameter", "optional_parameter")
            ]
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_method",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_async=any(c.type == "async" for c in node.children),
        )

    def _parse_function(self, node: _TreeNode, lines: list[str]) -> FunctionInfo:
        name_node = self._child_by_type(node, "identifier")
        params_node = self._child_by_type(node, "formal_parameters")
        params = []
        if params_node:
            params = [
                self._node_text(c)
                for c in params_node.children
                if c.type in ("required_parameter", "optional_parameter", "identifier")
            ]
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_function",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_async=any(c.type == "async" for c in node.children),
        )

    def _parse_arrow_assign(self, node: _TreeNode, lines: list[str]) -> FunctionInfo | None:
        arrow = self._find_first(node, "arrow_function")
        if not arrow:
            return None
        name_node = self._child_by_type(node, "identifier")
        declarator = self._find_first(node, "variable_declarator")
        if declarator and not name_node:
            name_node = self._find_first_at_depth(declarator, "identifier", 2)
        params_node = self._child_by_type(arrow, "formal_parameters")
        params = []
        if params_node:
            params = [
                self._node_text(c)
                for c in params_node.children
                if c.type in ("required_parameter", "optional_parameter", "identifier")
            ]
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_arrow",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=max(arrow.end_point[0], node.end_point[0]),
            params=params,
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=arrow.end_point[0] - arrow.start_point[0],
            complexity=1,
            is_async=any(c.type == "async" for c in arrow.children),
        )

    def _find_first(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return find_first(node, node_type)

    def _find_first_at_depth(self, node: _TreeNode, node_type: str, max_depth: int) -> _TreeNode | None:
        if node.type == node_type:
            return node
        if max_depth <= 0:
            return None
        for child in node.children:
            found = self._find_first_at_depth(child, node_type, max_depth - 1)
            if found:
                return found
        return None

    def _find_all(self, node: _TreeNode, node_type: str) -> list[_TreeNode]:
        found: list[_TreeNode] = []
        for child in node.children:
            if child.type == node_type:
                found.append(child)
            found.extend(self._find_all(child, node_type))
        return found
