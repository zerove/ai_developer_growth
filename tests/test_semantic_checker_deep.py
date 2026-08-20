"""Deep coverage for semantic_checker.py complex paths (_check_complexity, _check_missing_docstrings, _calculate_metrics)."""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.ast_parser import (
    ClassInfo,
    FileAST,
    FunctionInfo,
    ImportInfo,
)
from tools.scripts.rules_engine.semantic_checker import SemanticChecker


def _make_ast(
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    imports: list[ImportInfo] | None = None,
) -> FileAST:
    return FileAST(
        language="python",
        functions=functions or [],
        classes=classes or [],
        imports=imports or [],
        global_variables=[],
        error_nodes=[],
        total_nodes=0,
        parse_time_ms=0.0,
    )


class TestSemanticCheckerDeep:
    """Cover remaining semantic_checker paths (69%→90%)."""

    def test_check_complexity_long_function(self):
        """_check_complexity flags functions exceeding line limit."""
        func = FunctionInfo(
            name="long_function",
            line=1,
            col=0,
            end_line=60,
            params=["a", "b"],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=55,
            complexity=1,
        )
        checker = SemanticChecker()
        issues = checker._check_complexity(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        longs = [i for i in issues if i.rule_id == "long-function"]
        assert len(longs) == 1
        assert "long_function" in longs[0].message

    def test_check_complexity_high_cyclomatic(self):
        """_check_complexity flags high cyclomatic complexity."""
        func = FunctionInfo(
            name="complex_func",
            line=1,
            col=0,
            end_line=20,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=15,
            complexity=15,
        )
        checker = SemanticChecker()
        issues = checker._check_complexity(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        highs = [i for i in issues if i.rule_id == "high-complexity"]
        assert len(highs) == 1
        assert "complexity 15" in highs[0].message

    def test_check_complexity_both_violations(self):
        """A function can violate both length AND complexity."""
        func = FunctionInfo(
            name="both_violations",
            line=1,
            col=0,
            end_line=80,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=70,
            complexity=20,
        )
        checker = SemanticChecker()
        issues = checker._check_complexity(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        rule_ids = {i.rule_id for i in issues}
        assert "long-function" in rule_ids
        assert "high-complexity" in rule_ids

    def test_check_complexity_clean(self):
        """Well-written functions produce no issues."""
        func = FunctionInfo(
            name="clean_func",
            line=1,
            col=0,
            end_line=10,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=5,
            complexity=1,
        )
        checker = SemanticChecker()
        issues = checker._check_complexity(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        assert issues == []

    def test_check_missing_docstrings_public_func(self):
        """Public function without docstring is flagged."""
        func = FunctionInfo(
            name="public_api",
            line=1,
            col=0,
            end_line=5,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=3,
            complexity=1,
        )
        checker = SemanticChecker()
        issues = checker._check_missing_docstrings(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        assert len(issues) == 1
        assert "public_api" in issues[0].message

    def test_check_missing_docstrings_private_func_ok(self):
        """Private function without docstring is NOT flagged."""
        func = FunctionInfo(
            name="_internal",
            line=1,
            col=0,
            end_line=5,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=3,
            complexity=1,
        )
        checker = SemanticChecker()
        issues = checker._check_missing_docstrings(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        assert issues == []

    def test_check_missing_docstrings_with_docstring_ok(self):
        """Function with docstring is NOT flagged."""
        func = FunctionInfo(
            name="documented_func",
            line=1,
            col=0,
            end_line=10,
            params=[],
            decorators=[],
            return_type=None,
            docstring="This function does X.",
            body_lines=5,
            complexity=1,
        )
        checker = SemanticChecker()
        issues = checker._check_missing_docstrings(
            {"test.py": _make_ast(functions=[func])}, Path(".")
        )
        assert issues == []

    def test_check_missing_docstrings_public_class(self):
        """Public class without docstring is flagged."""
        cls = ClassInfo(
            name="PublicClass",
            line=1,
            col=0,
            end_line=20,
            bases=[],
            decorators=[],
            docstring=None,
            methods=[],
            body_lines=15,
        )
        checker = SemanticChecker()
        issues = checker._check_missing_docstrings(
            {"test.py": _make_ast(classes=[cls])}, Path(".")
        )
        assert len(issues) == 1
        assert "PublicClass" in issues[0].message

    def test_calculate_metrics_with_data(self):
        """_calculate_metrics computes correct aggregates."""
        f1 = FunctionInfo(
            name="short_func",
            line=1,
            col=0,
            end_line=5,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=3,
            complexity=1,
        )
        f2 = FunctionInfo(
            name="long_func",
            line=10,
            col=0,
            end_line=70,
            params=[],
            decorators=[],
            return_type=None,
            docstring=None,
            body_lines=60,
            complexity=15,
        )
        imp = ImportInfo(module="os", names=["path"], line=1, is_from=True, level=0)
        file_ast = _make_ast(functions=[f1, f2], imports=[imp])
        checker = SemanticChecker()
        metrics = checker._calculate_metrics({"test.py": file_ast})
        assert metrics.total_functions == 2
        assert metrics.total_imports == 1
        assert metrics.max_function_length == 60
        assert metrics.max_complexity == 15
        assert metrics.long_functions == ["long_func"]
        assert metrics.complex_functions == ["long_func"]

    def test_calculate_metrics_empty(self):
        """_calculate_metrics on empty ASTs returns zeros."""
        checker = SemanticChecker()
        metrics = checker._calculate_metrics({})
        assert metrics.total_functions == 0
        assert metrics.total_lines == 0
