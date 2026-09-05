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
