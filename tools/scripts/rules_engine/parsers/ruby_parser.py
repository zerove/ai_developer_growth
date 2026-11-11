"""Ruby 语言 tree-sitter 解析器：提取方法、类方法与类/模块定义。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, node_text
from tools.scripts.rules_engine.ast_nodes import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class RubyParser(BaseParser):
    """解析 Ruby 的 method/singleton_method 与 class/module 定义。"""

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        if root_node is not None:
            self._walk(root_node, lines, functions, classes, None)
        return functions, classes

    def _walk(
        self,
        node: _TreeNode,
        lines: list[str],
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        class_name: str | None,
    ) -> None:
        if node is None:
            return
        if node.type == "class":
            info = self._parse_class(node, lines)
            classes.append(info)
            methods: list[FunctionInfo] = []
            self._collect_methods(node, methods, classes, info.name)
            info.methods = list(methods)
            functions.extend(methods)
            return
        if node.type == "module":
            name = self._module_name(node)
            module_methods: list[FunctionInfo] = []
            self._collect_methods(node, module_methods, classes, name)
            functions.extend(module_methods)
            return  # 模块不进 classes（非实例化类型）
        if node.type == "method":
            functions.append(self._parse_method(node, lines, class_name))
            return
        if node.type == "singleton_method":
            functions.append(self._parse_singleton(node, lines, class_name))
            return
        for child in node.children:
            if child is not None:
                self._walk(child, lines, functions, classes, class_name)

    def _collect_methods(
        self,
        node: _TreeNode,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        owner: str,
    ) -> None:
        """在类/模块体内收集方法；嵌套 class/module 递归为独立类。"""
        if node is None:
            return
        if node.type in ("class", "module"):
            for child in node.children:
                if child is None:
                    continue
                if child.type == "body_statement":
                    self._scan_body(child, functions, classes, owner)
            return
        for child in node.children:
            if child is not None:
                self._collect_methods(child, functions, classes, owner)

    def _scan_body(
        self,
        body: _TreeNode,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        owner: str,
    ) -> None:
        """扫描 body_statement：方法归 owner，嵌套类/模块递归处理。"""
        for child in body.children:
            if child is None:
                continue
            if child.type == "method":
                functions.append(self._parse_method(child, [], owner))
            elif child.type == "singleton_method":
                functions.append(self._parse_singleton(child, [], owner))
            elif child.type == "class":
                info = self._parse_class(child, [])
                classes.append(info)
                methods: list[FunctionInfo] = []
                self._collect_methods(child, methods, classes, info.name)
                info.methods = list(methods)
                functions.extend(methods)
            elif child.type == "module":
                name = self._module_name(child)
                methods = []
                self._collect_methods(child, methods, classes, name)
                functions.extend(methods)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode) -> str:
        return node_text(node)

    def _constant_name(self, node: _TreeNode) -> str | None:
        """从 class/module 节点取名称（constant / scope_resolution）。"""
        name_node = self._child_by_type(node, "constant")
        if name_node is not None:
            return self._node_text(name_node)
        scoped = self._child_by_type(node, "scope_resolution")
        if scoped is not None:
            return self._node_text(scoped).lstrip(":")
        return None

    def _module_name(self, node: _TreeNode) -> str:
        name = self._constant_name(node)
        return name if name else "extracted_module"

    def _superclass_names(self, node: _TreeNode) -> list[str]:
        bases: list[str] = []
        superclass = self._child_by_type(node, "superclass")
        if superclass is not None:
            # superclass 节点含 "<" 与类名，取最后一个非 "<" 子节点的文本
            name_parts = [
                self._node_text(c) for c in superclass.children if c is not None and self._node_text(c) != "<"
            ]
            if name_parts:
                bases.append(name_parts[-1].lstrip(":"))
            else:
                text = self._node_text(superclass).strip().lstrip("<").strip()
                if text:
                    bases.append(text.lstrip(":"))
        return bases

    def _parse_class(self, node: _TreeNode, lines: list[str]) -> ClassInfo:
        return ClassInfo(
            name=self._constant_name(node) or "extracted_class",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=self._superclass_names(node),
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _params_of(self, node: _TreeNode) -> list[str]:
        params: list[str] = []
        params_node = self._child_by_type(node, "method_parameters")
        if params_node is not None:
            for child in params_node.children:
                if child.type in (
                    "identifier",
                    "optional_parameter",
                    "required_parameter",
                    "keyword_parameter",
                    "splat_parameter",
                    "block_parameter",
                ):
                    params.append(self._node_text(child).lstrip("&*"))
        return params

    def _parse_method(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo:
        name_node = self._child_by_type(node, "identifier")
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_method",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=self._params_of(node),
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=True,
            class_name=class_name,
        )

    def _parse_singleton(self, node: _TreeNode, lines: list[str], class_name: str | None) -> FunctionInfo:
        info = self._parse_method(node, lines, class_name)
        # def self.xxx → 标记为类方法，名字加前缀以区分实例方法
        object_node = self._child_by_type(node, "self") or self._child_by_type(node, "identifier")
        name_node = self._child_by_type(node, "identifier")
        method_name = self._node_text(name_node) if name_node else info.name
        if object_node is not None and object_node.type == "self":
            info.name = f"self.{method_name}"
        else:
            info.name = method_name
        return info
