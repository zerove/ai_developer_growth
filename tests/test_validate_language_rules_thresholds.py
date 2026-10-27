# 拆分自 tests/test_validate_language_rules.py

"""validate_language_rules 核心校验用例。

覆盖 Issue/ValidationResult/规则加载/anti-pattern/命名/阈值/嵌套/AST/
圈复杂度/语言检测/文件与目录校验/JSON 输出。

各语言 anti-pattern 规则用例见 test_language_rules_languages.py。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.scripts.validate_language_rules import (
    _calc_cyclomatic_complexity,
    _max_nesting_depth,
    _max_python_indent_depth,
    check_python_ast,
    check_thresholds,
    load_rules,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def python_rules():
    """Load Python rules."""
    return load_rules("python")


@pytest.fixture
def ts_rules():
    """Load TypeScript rules."""
    return load_rules("typescript")


@pytest.fixture
def rust_rules():
    """Load Rust rules."""
    return load_rules("rust")


@pytest.fixture
def go_rules():
    """Load Go rules."""
    return load_rules("go")


class TestThresholds:
    def test_line_length_detected(self, python_rules):
        lines = ["x = " + "a" * 130]
        issues = check_thresholds(lines, python_rules, "test.py")
        line_issues = [i for i in issues if "line-length" in i.rule_id]
        assert len(line_issues) == 1

    def test_line_length_ok(self, python_rules):
        lines = ["x = 'short'"]
        issues = check_thresholds(lines, python_rules, "test.py")
        line_issues = [i for i in issues if "line-length" in i.rule_id]
        assert len(line_issues) == 0

    def test_file_length_detected(self, python_rules):
        lines = [f"line_{i}" for i in range(600)]
        issues = check_thresholds(lines, python_rules, "test.py")
        file_issues = [i for i in issues if "file-length" in i.rule_id]
        assert len(file_issues) == 1

    def test_file_length_ok(self, python_rules):
        lines = [f"line_{i}" for i in range(100)]
        issues = check_thresholds(lines, python_rules, "test.py")
        file_issues = [i for i in issues if "file-length" in i.rule_id]
        assert len(file_issues) == 0

    def test_function_length_detected(self, python_rules):
        lines = ["def long_function():"] + ["    x = 1"] * 60
        issues = check_thresholds(lines, python_rules, "test.py")
        func_issues = [i for i in issues if "func-length" in i.rule_id]
        assert len(func_issues) == 1

    def test_nesting_depth_detected(self, python_rules):
        # Python indentation-based nesting
        lines = [
            "def f():",
            "    if True:",
            "        for i in range(10):",
            "            if i > 5:",
            "                while True:",
            "                    pass",
        ]
        issues = check_thresholds(lines, python_rules, "test.py")
        nest_issues = [i for i in issues if "nesting" in i.rule_id]
        assert len(nest_issues) == 1


class TestNestingDepth:
    def test_flat_code(self):
        assert _max_nesting_depth(["x = 1"]) == 0

    def test_one_level(self):
        assert _max_nesting_depth(["if True:", "    x = 1"]) == 0

    def test_brackets(self):
        lines = ["result = func("]
        depth = _max_nesting_depth(lines)
        assert depth >= 1

    def test_nested_brackets(self):
        lines = ["result = func(a, inner("]
        depth = _max_nesting_depth(lines)
        assert depth >= 2

    def test_python_indent_depth(self):
        lines = [
            "def f():",
            "    if True:",
            "        for i in range(10):",
            "            if i > 5:",
            "                while True:",
            "                    pass",
        ]
        depth = _max_python_indent_depth(lines)
        assert depth == 5  # 20 spaces / 4 = 5


class TestPythonAST:
    def test_syntax_error_detected(self, tmp_dir):
        filepath = tmp_dir / "bad.py"
        filepath.write_text("def f(\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) >= 1

    def test_missing_return_type(self, tmp_dir):
        filepath = tmp_dir / "no_type.py"
        filepath.write_text("def public_func():\n    return 1\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-no-return-type" in ids

    def test_private_func_no_type_ok(self, tmp_dir):
        filepath = tmp_dir / "priv.py"
        filepath.write_text("def _private():\n    return 1\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        type_issues = [i for i in issues if i.rule_id == "py-ast-no-return-type"]
        assert len(type_issues) == 0

    def test_missing_param_type(self, tmp_dir):
        filepath = tmp_dir / "no_param.py"
        filepath.write_text("def f(x: int, y) -> int:\n    return x\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-no-param-type" in ids

    def test_self_param_not_checked(self, tmp_dir):
        filepath = tmp_dir / "cls.py"
        filepath.write_text("class A:\n    def method(self) -> None:\n        pass\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        param_issues = [i for i in issues if i.rule_id == "py-ast-no-param-type"]
        assert len(param_issues) == 0

    def test_function_too_long(self, tmp_dir):
        filepath = tmp_dir / "long.py"
        body = "\n".join(["    x = 1"] * 60)
        filepath.write_text(f"def long_func():\n{body}\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-function-length" in ids

    def test_too_many_args(self, tmp_dir):
        filepath = tmp_dir / "args.py"
        filepath.write_text("def f(a, b, c, d, e, f, g, h) -> int:\n    return 1\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-function-args" in ids

    def test_cyclomatic_complexity(self, tmp_dir):
        filepath = tmp_dir / "complex.py"
        filepath.write_text(
            "def complex_func(x: int) -> int:\n"
            "    if x > 0:\n"
            "        if x > 10:\n"
            "            for i in range(x):\n"
            "                if i % 2 == 0:\n"
            "                    while i > 0:\n"
            "                        i -= 1\n"
            "                elif i % 3 == 0:\n"
            "                    pass\n"
            "                elif i % 5 == 0:\n"
            "                    pass\n"
            "                elif i % 7 == 0:\n"
            "                    pass\n"
            "                elif i % 11 == 0:\n"
            "                    pass\n"
            "    return x\n"
        )
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-complexity" in ids


class TestCyclomaticComplexity:
    def test_simple_function(self, tmp_dir):
        filepath = tmp_dir / "simple.py"
        filepath.write_text("def f():\n    return 1\n")
        tree = __import__("ast").parse(filepath.read_text())
        func = tree.body[0]
        assert _calc_cyclomatic_complexity(func) == 1

    def test_if_branches(self, tmp_dir):
        filepath = tmp_dir / "branch.py"
        filepath.write_text(
            "def f(x):\n    if x > 0:\n        return 1\n    elif x < 0:\n        return -1\n    return 0\n"
        )
        tree = __import__("ast").parse(filepath.read_text())
        func = tree.body[0]
        c = _calc_cyclomatic_complexity(func)
        assert c >= 3  # base + 2 branches
