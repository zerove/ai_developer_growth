"""Tests for ast_parser deep-AST recursion safety (Phase 33b-7).

Covers:
- _walk_python_functions: 深度嵌套 binary_expression (1+1+1+...) 不触发 RecursionError
- _walk_classes: 深度嵌套 class 不触发 RecursionError
- _walk_python_globals: 深度嵌套 global 赋值
- _walk_imports: 已有此 bug 风险
- 修复前所有 walk_* 函数是纯递归, 深度 AST 触发 RecursionError.

详见 ADR-048 Phase 33b-7 深度 AST 安全修复.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine.ast_parser import ASTParser


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


def _make_file(tmp_path: Path, code: str, suffix: str = ".py") -> Path:
    f = tmp_path / f"deep{suffix}"
    f.write_text(code)
    return f


class TestDeepBinaryExpression:
    """深度 binary_expression 嵌套 (例如 1+1+1+...)."""

    def test_chain_100_additions_no_recursion_error(self, parser: ASTParser, tmp_path: Path) -> None:
        """100 个加法链 (左结合) → parse 不抛 RecursionError."""
        code = "x = " + " + ".join("1" for _ in range(100))
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None, "100-chain 表达式应能解析"

    def test_chain_500_additions_no_recursion_error(self, parser: ASTParser, tmp_path: Path) -> None:
        """500 个加法链 → parse 不抛 RecursionError."""
        code = "x = " + " + ".join("1" for _ in range(500))
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None, "500-chain 表达式应能解析"

    def test_chain_1000_additions_no_recursion_error(self, parser: ASTParser, tmp_path: Path) -> None:
        """1000 个加法链 → parse 不抛 RecursionError (原 RecursionError 边界)."""
        code = "x = " + " + ".join("1" for _ in range(1000))
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None, "1000-chain 表达式应能解析"

    def test_chain_2000_additions_no_recursion_error(self, parser: ASTParser, tmp_path: Path) -> None:
        """2000 个加法链 (深度极限) → parse 不抛 RecursionError."""
        code = "x = " + " + ".join("1" for _ in range(2000))
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None, "2000-chain 表达式应能解析"


class TestDeepNestedClass:
    """深度嵌套 class 定义 (旧递归 bug 风险)."""

    def test_nested_class_depth_50(self, parser: ASTParser, tmp_path: Path) -> None:
        """50 层嵌套 class → parse 不抛 RecursionError."""
        code = "\n".join(f"{'    ' * i}class C{i}:\n{'    ' * (i + 1)}x = 1" for i in range(50))
        # 需要最后一层是有效语句 (而不是空的 class body)
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None


class TestDeepFunctionNesting:
    """深度嵌套函数 (func inside func)."""

    def test_nested_function_depth_50(self, parser: ASTParser, tmp_path: Path) -> None:
        """50 层嵌套函数 → parse 不抛 RecursionError."""
        indent = "    "
        lines = []
        for i in range(50):
            lines.append(f"{indent * i}def f{i}():\n{indent * (i + 1)}pass\n")
        code = "".join(lines)
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None


class TestExistingEdgeCases:
    """已有边界场景回归."""

    def test_empty_file(self, parser: ASTParser, tmp_path: Path) -> None:
        """空文件 → parse=True (与之前一致)."""
        f = _make_file(tmp_path, "")
        result = parser.parse_file(f, language="python")
        assert result is not None

    def test_unicode_file(self, parser: ASTParser, tmp_path: Path) -> None:
        """Unicode 内容 → parse=True."""
        f = _make_file(tmp_path, '# 中文注释\nx = "你好"\n')
        result = parser.parse_file(f, language="python")
        assert result is not None

    def test_10k_lines_file(self, parser: ASTParser, tmp_path: Path) -> None:
        """10K 行文件 → parse=True."""
        code = "x = 1\n" * 10000
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None


class TestMultilangDeepAST:
    """多语言深度 AST 安全性 (Phase 33b-7 扩展).

    覆盖 _walk_js_functions / _walk_rust_functions / _walk_go_functions / _walk_generic_functions.
    """

    def test_js_deep_arrow_chain(self, parser: ASTParser, tmp_path: Path) -> None:
        """JS 深度链式表达式 (1+1+1+... * 500) 不爆栈."""
        code = "const x = " + " + ".join("1" for _ in range(500)) + ";"
        f = _make_file(tmp_path, code, suffix=".js")
        result = parser.parse_file(f, language="javascript")
        assert result is not None

    def test_rust_deep_binary_chain(self, parser: ASTParser, tmp_path: Path) -> None:
        """Rust 深度链式表达式 不爆栈."""
        code = "fn main() { let x = " + " + ".join("1" for _ in range(500)) + "; }"
        f = _make_file(tmp_path, code, suffix=".rs")
        result = parser.parse_file(f, language="rust")
        assert result is not None

    def test_go_deep_binary_chain(self, parser: ASTParser, tmp_path: Path) -> None:
        """Go 深度链式表达式 不爆栈."""
        code = "package main\nfunc main() { x := " + " + ".join("1" for _ in range(500)) + " }"
        f = _make_file(tmp_path, code, suffix=".go")
        result = parser.parse_file(f, language="go")
        assert result is not None

    def test_js_nested_class_50(self, parser: ASTParser, tmp_path: Path) -> None:
        """JS 50 层嵌套 class 不爆栈 (迭代化 _walk_js_functions 验证)."""
        code = "\n".join(f"{'    ' * i}class C{i} {{ {' ' * (i + 1)}x = 1; {'}'}" for i in range(50))
        f = _make_file(tmp_path, code, suffix=".js")
        result = parser.parse_file(f, language="javascript")
        assert result is not None


class TestComplexityCalculationSafety:
    """_count_branching_static / _estimate_complexity_static 深度安全 (Phase 33b-7)."""

    def test_complexity_deep_boolean_chain(self, parser: ASTParser, tmp_path: Path) -> None:
        """深度 boolean_operation 链 (a and b and c...) 不爆栈 + 不被计入复杂度.

        boolean_operation 不在 branching_types 集合中 (设计选择),
        所以无论链多深, complexity 应不变. 关键验证是不爆栈.
        """
        # 500 个 and 链
        expr = " and ".join(f"a{i}" for i in range(500))
        code = f"def f():\n    return {expr}\n"
        f = _make_file(tmp_path, code)
        # 关键: parse 不爆栈
        result = parser.parse_file(f, language="python")
        assert result is not None
        # boolean_operation 不计入 branching, complexity=1
        assert result.functions[0].complexity == 1

    def test_complexity_deep_conditional(self, parser: ASTParser, tmp_path: Path) -> None:
        """深度 conditional_expression 链 (a if b else c if d else e...) 不爆栈."""
        code = "def f():\n    x = 1" + " if True else " * 500 + "2\n"
        f = _make_file(tmp_path, code)
        result = parser.parse_file(f, language="python")
        assert result is not None
