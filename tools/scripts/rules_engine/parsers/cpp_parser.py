"""C/C++ 语言 tree-sitter 解析器：提取函数、类方法与类/结构体定义。"""

from __future__ import annotations

from tools.scripts.rules_engine.ast_nodes import ClassInfo, FunctionInfo, _TreeNode

from .base import BaseParser


class CppParser(BaseParser):
    """解析 C/C++ 的函数定义、类内方法与 class/struct 定义。

    tree-sitter-cpp 节点类型:
    - function_definition (自由函数与类内定义的方法)
    - declaration 中的 function_declarator (仅声明的成员函数)
    - class_specifier / struct_specifier (类与结构体)
    """

    def parse(self, root_node: _TreeNode, lines: list[str]) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        if root_node is not None:
            self._walk(root_node, functions, classes, None)
        return functions, classes

    def _walk(
        self,
        node: _TreeNode,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        class_name: str | None,
    ) -> None:
        if node is None:
            return
        if node.type in ("class_specifier", "struct_specifier"):
            info = self._parse_class(node)
            if info is not None:
                classes.append(info)
                inner: list[FunctionInfo] = []
                self._walk_members(node, inner, info.name)
                info.methods = list(inner)
                functions.extend(inner)
                return
        if node.type == "function_definition":
            func = self._parse_function(node, class_name)
            if func is not None:
                functions.append(func)
            return  # 函数体内部不深入(避免局部 lambda 重复归属顶层)
        for child in node.children:
            if child is not None:
                self._walk(child, functions, classes, class_name)

    def _walk_members(
        self,
        node: _TreeNode,
        functions: list[FunctionInfo],
        class_name: str,
    ) -> None:
        """Walk class/struct members and collect methods (V2.21 P5-58 拆分: 抽 _parse_function_definition + _parse_declaration_method)."""
        if node is None:
            return
        if node.type == "function_definition":
            self._parse_function_definition(node, functions, class_name)
            return
        if node.type == "field_declaration" or node.type == "declaration":
            if self._parse_declaration_method(node, functions, class_name):
                return
        for child in node.children:
            if child is not None:
                self._walk_members(child, functions, class_name)

    def _parse_function_definition(self, node: _TreeNode, functions: list[FunctionInfo], class_name: str) -> None:
        """处理 function_definition 节点 (方法级 helper).

        Args:
            node: function_definition 节点
            functions: 累积目标列表
            class_name: 类名
        """
        func = self._parse_function(node, class_name)
        if func is not None:
            functions.append(func)

    def _parse_declaration_method(self, node: _TreeNode, functions: list[FunctionInfo], class_name: str) -> bool:
        """处理声明式方法 (virtual void run(int speed);), 返回是否找到 (方法级 helper).

        Args:
            node: field_declaration/declaration 节点
            functions: 累积目标列表
            class_name: 类名

        Returns:
            True 表示找到声明式方法, False 否则
        """
        for child in node.children:
            if child is not None and child.type == "function_declarator":
                name_node = self._field(child, "declarator")
                if name_node is not None:
                    functions.append(
                        FunctionInfo(
                            name=self._node_text(name_node),
                            line=node.start_point[0],
                            col=node.start_point[1],
                            end_line=node.end_point[0],
                            params=self._params_of(child),
                            decorators=[],
                            return_type=None,
                            docstring=None,
                            body_lines=0,
                            complexity=1,
                            is_method=True,
                            class_name=class_name,
                        )
                    )
                return True
        return False

    def _field(self, node: _TreeNode, name: str) -> _TreeNode | None:
        """child_by_field_name 的安全封装(_TreeNode 协议未声明该方法)。"""
        getter = getattr(node, "child_by_field_name", None)
        return getter(name) if callable(getter) else None

    def _parse_class(self, node: _TreeNode) -> ClassInfo | None:
        """Parse C++ class/struct (V2.22 P6-8 拆分: 抽 _extract_class_bases, 方法级 helper)."""
        name_node = self._field(node, "name")
        if name_node is None:
            return None
        bases = self._extract_class_bases(node)
        return ClassInfo(
            name=self._node_text(name_node),
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            bases=bases,
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=node.end_point[0] - node.start_point[0],
        )

    def _extract_class_bases(self, node: _TreeNode) -> list[str]:
        """提取 C++ class/struct 基类列表 (方法级 helper).

        Args:
            node: class_specifier 节点

        Returns:
            基类名列表
        """
        bases: list[str] = []
        base_list = next((c for c in node.children if c.type == "base_class_clause"), None)
        if base_list is None:
            return bases
        for child in base_list.children:
            if child is None or child.type in (":", ",", "comment"):
                continue
            if child.type == "access_specifier":
                # access_specifier 包住可见性关键字(public/private...), 其后兄弟才是类型
                continue
            if child.type in ("type_identifier", "qualified_identifier", "namespace_identifier", "dependent_type"):
                bases.append(self._node_text(child))
        return bases

    def _parse_function(self, node: _TreeNode, class_name: str | None) -> FunctionInfo | None:
        declarator = self._field(node, "declarator")
        if declarator is None:
            return None
        # function_definition → function_declarator → identifier / field_identifier
        name = self._find_declarator_name(declarator)
        if name is None:
            return None
        type_node = self._field(node, "type")
        return_type = self._node_text(type_node) if type_node is not None else None
        return FunctionInfo(
            name=name,
            line=node.start_point[0],
            col=node.start_point[1],
            end_line=node.end_point[0],
            params=self._params_of(declarator),
            decorators=[],
            return_type=return_type,
            docstring=None,
            body_lines=node.end_point[0] - node.start_point[0],
            complexity=1,
            is_method=class_name is not None,
            class_name=class_name,
        )

    def _find_declarator_name(self, declarator: _TreeNode) -> str | None:
        """从 declarator 链中取函数名(pointer/array 包装需剥开)。"""
        if declarator is None:
            return None
        if declarator.type in ("identifier", "field_identifier"):
            return self._node_text(declarator)
        if declarator.type in (
            "function_declarator",
            "pointer_declarator",
            "reference_declarator",
            "parenthesized_declarator",
        ):
            inner = self._field(declarator, "declarator")
            if inner is not None:
                return self._find_declarator_name(inner)
        for child in declarator.children:
            if child is not None:
                found = self._find_declarator_name(child)
                if found is not None:
                    return found
        return None

    def _params_of(self, declarator: _TreeNode) -> list[str]:
        param_list = self._field(declarator, "parameters")
        params: list[str] = []
        if param_list is not None:
            for child in param_list.children:
                if child is not None and child.type not in (",", "(", ")"):
                    text = self._node_text(child)
                    # 参数名 = 最后一段标识符; 简化取整段文本
                    params.append(text.split()[-1].lstrip("*&") if text else "")
        return params

    def _node_text(self, node: _TreeNode) -> str:
        text = getattr(node, "text", None)
        if isinstance(text, bytes):
            return text.decode(errors="replace")
        if isinstance(text, str):
            return text
        # 回退: 通过 start/end_point 从源码行重建(协议外属性不存在时)
        return ""
