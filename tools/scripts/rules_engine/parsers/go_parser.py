"""Go 语言 tree-sitter 解析器：提取函数、方法与结构体。"""

from __future__ import annotations

from tools.scripts._common import child_by_type, find_first, node_text
from tools.scripts.rules_engine.ast_parser import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class GoParser(BaseParser):
    """解析 Go 的 func 声明、方法与 type struct 定义。"""

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        if root_node is not None:
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
        if node.type == "function_declaration":
            functions.append(self._parse_func(node, lines))
        elif node.type == "method_declaration":
            functions.append(self._parse_method(node, lines))
        elif node.type in ("type_spec",):
            info = self._parse_struct(node, lines)
            if info:
                classes.append(info)
        for child in node.children:
            if child is not None:
                self._walk(child, lines, functions, classes)

    def _child_by_type(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return child_by_type(node, node_type)

    def _node_text(self, node: _TreeNode) -> str:
        return node_text(node)

    def _parse_func(self, node: _TreeNode, lines: list[str]) -> FunctionInfo:
        name_node = self._child_by_type(node, "identifier")
        params_node = self._child_by_type(node, "parameter_list")
        return FunctionInfo(
            name=self._node_text(name_node) if name_node else "extracted_func",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=self._collect_params(params_node) if params_node else [],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
        )

    def _parse_method(self, node: _TreeNode, lines: list[str]) -> FunctionInfo:
        """Parse Go method (V2.21 P5-57 拆分: 抽 _extract_receiver_name + _build_method_info, 方法级 helper)."""
        name_node = self._child_by_type(node, "field_identifier")
        receiver = self._child_by_type(node, "parameter_list")
        receiver_name = self._extract_receiver_name(receiver) if receiver else ""
        params_node = [c for c in node.children if c.type == "parameter_list"]
        return self._build_method_info(node, name_node, receiver_name, params_node)

    def _extract_receiver_name(self, receiver: _TreeNode) -> str:
        """从 receiver parameter_list 提取 receiver type 名称 (方法级 helper).

        Args:
            receiver: parameter_list 节点

        Returns:
            receiver 类型名 (无则空串)
        """
        for child in receiver.children:
            if child.type == "parameter_declaration":
                pointer = self._child_by_type(child, "pointer_type")
                target = pointer or child
                ident = self._find_first(target, "type_identifier")
                return self._node_text(ident) if ident else ""
        return ""

    def _build_method_info(
        self,
        node: _TreeNode,
        name_node: _TreeNode | None,
        receiver_name: str,
        params_node: list[_TreeNode],
    ) -> FunctionInfo:
        """构造 Go method FunctionInfo (方法级 helper).

        Args:
            node: method 节点
            name_node: field_identifier 节点
            receiver_name: receiver 类型名
            params_node: 参数节点列表

        Returns:
            FunctionInfo 实例
        """
        return FunctionInfo(
            name=f"{receiver_name}.{self._node_text(name_node)}" if name_node else "extracted_method",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=self._collect_params(params_node[-1]) if params_node else [],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=True,
            class_name=receiver_name or None,
        )

    def _parse_struct(self, node: _TreeNode, lines: list[str]) -> ClassInfo | None:
        name_node = self._child_by_type(node, "type_identifier")
        struct_node = self._child_by_type(node, "struct_type")
        if not struct_node:
            return None
        return ClassInfo(
            name=self._node_text(name_node) if name_node else "extracted_struct",
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=[],
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _collect_params(self, params_node: _TreeNode) -> list[str]:
        params: list[str] = []
        for child in params_node.children:
            if child.type == "parameter_declaration":
                params.append(self._node_text(child))
        return params

    def _find_first(self, node: _TreeNode, node_type: str) -> _TreeNode | None:
        return find_first(node, node_type)
