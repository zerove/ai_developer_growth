"""Tests for semantic_checker SemanticChecker 私有方法 (Phase 33a-2).

覆盖私有方法 (估时 1h 子任务):
- _accumulate_function_metrics: 累加 metrics + 收集 long/complex 列表
- _accumulate_class_metrics: 累加 classes_without_docstring
- _compute_averages: 计算 avg_function_length + avg_complexity

详见 ADR-036 Phase 33 子任务分解 + ADR-040 (本次)。
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tools.scripts.rules_engine.semantic_checker import (
    ComplexityMetrics,
    SemanticChecker,
)


@dataclass
class FakeFunc:
    """Minimal FunctionInfo stub for testing metrics accumulation."""

    name: str
    body_lines: int = 10
    complexity: int = 5
    is_method: bool = False
    class_name: str = ""
    docstring: str | None = "fake docstring"
    line: int = 1


@dataclass
class FakeClass:
    """Minimal ClassInfo stub."""

    name: str
    docstring: str | None = "fake"
    line: int = 1


class TestAccumulateFunctionMetrics:
    """_accumulate_function_metrics() 累加单文件所有 function 的指标。"""

    def test_empty_functions_returns_initial_totals(self) -> None:
        """空函数列表 → 返回 (0, 0) 不变。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        total_length, total_complexity = checker._accumulate_function_metrics([], metrics, 0, 0)
        assert total_length == 0
        assert total_complexity == 0
        assert metrics.total_functions == 0

    def test_accumulates_body_lines_and_complexity(self) -> None:
        """累加 body_lines + complexity 到 total。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [FakeFunc("a", body_lines=10, complexity=3), FakeFunc("b", body_lines=20, complexity=7)]
        total_length, total_complexity = checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert total_length == 30
        assert total_complexity == 10

    def test_tracks_max_function_length(self) -> None:
        """记录最大 body_lines 到 metrics.max_function_length。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [
            FakeFunc("a", body_lines=20),
            FakeFunc("b", body_lines=50),  # max
            FakeFunc("c", body_lines=10),
        ]
        checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert metrics.max_function_length == 50

    def test_tracks_max_complexity(self) -> None:
        """记录最大 complexity 到 metrics.max_complexity。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [
            FakeFunc("a", complexity=3),
            FakeFunc("b", complexity=15),  # max
            FakeFunc("c", complexity=7),
        ]
        checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert metrics.max_complexity == 15

    def test_collects_long_functions_over_50(self) -> None:
        """>50 行的函数被收集到 long_functions。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [
            FakeFunc("a", body_lines=30),
            FakeFunc("b", body_lines=60),  # long
            FakeFunc("c", body_lines=100),  # long
        ]
        checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert sorted(metrics.long_functions) == ["b", "c"]

    def test_collects_complex_functions_over_10(self) -> None:
        """>10 complexity 的函数被收集到 complex_functions。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [
            FakeFunc("a", complexity=5),
            FakeFunc("b", complexity=12),  # complex
            FakeFunc("c", complexity=20),  # complex
        ]
        checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert sorted(metrics.complex_functions) == ["b", "c"]

    def test_counts_functions_without_docstring(self) -> None:
        """>0 个无 docstring 的 public function 被计数。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [
            FakeFunc("public_a", docstring=None),  # no doc
            FakeFunc("public_b", docstring="has"),
            FakeFunc("_private", docstring=None),  # private, 不计
        ]
        checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert metrics.functions_without_docstring == 1

    def test_method_name_uses_class_dot_notation(self) -> None:
        """method 在 long/complex 列表中用 ClassName.method 形式。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        funcs = [
            FakeFunc("my_method", body_lines=60, is_method=True, class_name="MyClass"),
        ]
        checker._accumulate_function_metrics(funcs, metrics, 0, 0)
        assert metrics.long_functions == ["MyClass.my_method"]


class TestAccumulateClassMetrics:
    """_accumulate_class_metrics() 累加 class 指标。"""

    def test_empty_classes_no_change(self) -> None:
        """空类列表 → 不修改 metrics。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        metrics.classes_without_docstring = 5  # pre-existing
        checker._accumulate_class_metrics([], metrics)
        assert metrics.classes_without_docstring == 5

    def test_counts_classes_without_docstring(self) -> None:
        """>0 个无 docstring 的 public class 被计数。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        classes = [
            FakeClass("PublicA", docstring=None),  # no doc
            FakeClass("PublicB", docstring="has"),
            FakeClass("_Private", docstring=None),  # private, 不计
        ]
        checker._accumulate_class_metrics(classes, metrics)
        assert metrics.classes_without_docstring == 1


class TestComputeAverages:
    """_compute_averages() 计算 avg。"""

    def test_no_functions_raises_division_by_zero(self) -> None:
        """真实行为: total_functions=0 仍执行除法, 抛 ZeroDivisionError。

        文档化的边界行为 (未防护)。Phase 33 refactor 候选。
        """
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        metrics.total_functions = 0
        with pytest.raises(ZeroDivisionError):
            checker._compute_averages(metrics, total_func_length=100, total_complexity=50)

    def test_computes_averages(self) -> None:
        """total_functions=2 → avg = total / 2。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        metrics.total_functions = 2
        checker._compute_averages(metrics, total_func_length=60, total_complexity=20)
        assert metrics.avg_function_length == 30.0
        assert metrics.avg_complexity == 10.0

    def test_floating_point_division(self) -> None:
        """非整除结果为浮点。"""
        checker = SemanticChecker()
        metrics = ComplexityMetrics()
        metrics.total_functions = 3
        checker._compute_averages(metrics, total_func_length=10, total_complexity=7)
        # 10/3 ≈ 3.333, 7/3 ≈ 2.333
        assert abs(metrics.avg_function_length - 3.333) < 0.01
        assert abs(metrics.avg_complexity - 2.333) < 0.01
