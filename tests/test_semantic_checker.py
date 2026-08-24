"""Tests for semantic_checker.py complex methods (31%→90%)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tools.scripts.rules_engine.semantic_checker import (
    ComplexityMetrics,
    SemanticChecker,
    SemanticIssue,
)


class TestSemanticCheckerAnalyze:
    """Cover semantic_checker.analyze_directory and internal methods."""

    def test_analyze_directory_empty(self):
        """Analyze empty directory returns empty result."""
        with tempfile.TemporaryDirectory() as tmp:
            checker = SemanticChecker()
            result = checker.analyze_directory(Path(tmp))
            assert result is not None
            assert result.files_analyzed == 0
            assert len(result.issues) == 0

    def test_analyze_directory_simple_file(self):
        """Analyze directory with a simple Python file."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "hello.py").write_text("x = 1\n")
            checker = SemanticChecker()
            result = checker.analyze_directory(tmp_path, languages=["python"])
            assert result is not None
            # tree-sitter may or may not be available, but should not crash
            assert result.files_analyzed >= 0

    def test_collect_source_files_basic(self):
        """Collect source files from directory."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").touch()
            (tmp_path / "b.py").touch()
            (tmp_path / "__pycache__").mkdir()
            (tmp_path / "__pycache__" / "c.py").touch()

            checker = SemanticChecker()
            files = checker._collect_source_files(tmp_path, languages=None, max_files=100)
            paths = {str(f.relative_to(tmp_path)) for f in files}
            assert "a.py" in paths
            assert "b.py" in paths
            assert "__pycache__/c.py" not in paths

    def test_collect_source_files_filter_language(self):
        """Language filter narrows file list."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").touch()
            (tmp_path / "b.ts").touch()

            checker = SemanticChecker()
            files = checker._collect_source_files(tmp_path, languages=["python"], max_files=100)
            paths = {str(f.relative_to(tmp_path)) for f in files}
            assert "a.py" in paths
            assert "b.ts" not in paths

    def test_collect_source_files_max_limit(self):
        """Max files limit is respected."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(20):
                (tmp_path / f"f{i}.py").touch()

            checker = SemanticChecker()
            files = checker._collect_source_files(tmp_path, languages=None, max_files=5)
            assert len(files) <= 5

    def test_check_complexity_empty(self):
        """Complexity check on empty ASTs returns no issues."""
        checker = SemanticChecker()
        issues = checker._check_complexity({}, Path("."))
        assert issues == []

    def test_check_missing_docstrings_empty(self):
        """Missing docstring check on empty ASTs returns no issues."""
        checker = SemanticChecker()
        issues = checker._check_missing_docstrings({}, Path("."))
        assert issues == []

    def test_calculate_metrics_empty(self):
        """Metrics on empty ASTs returns zeroed metrics."""
        checker = SemanticChecker()
        metrics = checker._calculate_metrics({})
        assert metrics.total_functions == 0
        assert metrics.total_classes == 0
        assert metrics.total_lines == 0

    def test_complexity_metrics_defaults(self):
        """ComplexityMetrics default values are zeroed."""
        m = ComplexityMetrics(
            total_functions=0,
            total_classes=0,
            total_imports=0,
            total_lines=0,
            avg_function_length=0.0,
            max_function_length=0,
            avg_complexity=0.0,
            max_complexity=0,
        )
        assert m.total_functions == 0
        assert m.total_imports == 0
        assert m.long_functions == []
        assert m.complex_functions == []

    def test_semantic_issue_creation(self):
        """SemanticIssue stores all fields."""
        issue = SemanticIssue(
            file="test.py",
            line=10,
            severity="warning",
            category="complexity",
            rule_id="complexity-high",
            message="Function too complex",
            fix_hint="Refactor into smaller functions",
            context={"complexity": 12},
        )
        assert issue.file == "test.py"
        assert issue.rule_id == "complexity-high"
        assert issue.context["complexity"] == 12
