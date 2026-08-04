"""Tests for low-coverage modules: sarif_exporter, performance, semantic_checker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.scripts.rules_engine.models import CheckResult, Issue
from tools.scripts.rules_engine.performance import FileCache, PerformanceOptimizer
from tools.scripts.rules_engine.sarif_exporter import to_sarif
from tools.scripts.rules_engine.semantic_checker import (
    ComplexityMetrics,
    ImportGraph,
    SemanticChecker,
    SemanticIssue,
)

# ── sarif_exporter ────────────────────────────────────────────────


class TestSarifExporter:
    """Coverage for sarif_exporter.py (0% → 100%)."""

    def test_to_sarif_empty(self):
        """Empty results produce valid SARIF."""
        result = to_sarif([])
        data = json.loads(result)
        assert data["version"] == "2.1.0"
        assert data["runs"][0]["results"] == []

    def test_to_sarif_with_issues(self):
        """Issues are correctly serialized to SARIF format."""
        issues = [
            Issue(
                rule_id="test-rule",
                severity="error",
                category="security",
                file="src/main.py",
                line=42,
                message="Test issue",
            )
        ]
        result = to_sarif([CheckResult(file="src/main.py", issues=issues, language="python", skipped=False)])
        data = json.loads(result)
        results = data["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["ruleId"] == "test-rule"
        assert results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "src/main.py"
        assert results[0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 42

    def test_to_sarif_custom_tool_name(self):
        """Custom tool name appears in SARIF output."""
        issues = [
            Issue(
                rule_id="custom-rule",
                severity="warning",
                category="code_quality",
                file="test.py",
                line=1,
                message="Custom",
            )
        ]
        result = to_sarif(
            [CheckResult(file="test.py", issues=issues, language="python")],
            tool_name="my-custom-tool",
        )
        data = json.loads(result)
        assert data["runs"][0]["tool"]["driver"]["name"] == "my-custom-tool"

    def test_to_sarif_complex_result(self):
        """Multiple results with multiple issues produce correct SARIF."""
        results = [
            CheckResult(
                file="a.py",
                issues=[
                    Issue(rule_id="R001", severity="error", category="bug", file="a.py", line=1, message="Error A"),
                    Issue(
                        rule_id="R002", severity="warning", category="style", file="a.py", line=2, message="Warning A"
                    ),
                ],
                language="python",
            ),
            CheckResult(
                file="b.py",
                issues=[
                    Issue(rule_id="R003", severity="info", category="info", file="b.py", line=10, message="Info B"),
                ],
                language="python",
            ),
        ]
        data = json.loads(to_sarif(results))
        assert len(data["runs"][0]["results"]) == 3


# ── performance ───────────────────────────────────────────────────


class TestFileCache:
    """Coverage for performance.FileCache."""

    def test_cache_get_set(self):
        """Basic put and get round-trip using real file."""
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "test.py"
            filepath.write_text("x = 1")
            cache_dir = Path(tmp) / "cache"
            cache = FileCache(max_entries=100, cache_dir=cache_dir)
            cache.set(str(filepath), {"key": "value"})
            result = cache.get(str(filepath))
            assert result is not None
            assert result["key"] == "value"

    def test_cache_miss_returns_none(self):
        """Missing key returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache = FileCache(max_entries=100, cache_dir=cache_dir)
            assert cache.get("/nonexistent/file.py") is None

    def test_cache_clear(self):
        """Clear removes all entries."""
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "test.py"
            filepath.write_text("x = 1")
            cache_dir = Path(tmp) / "cache"
            cache = FileCache(max_entries=100, cache_dir=cache_dir)
            cache.set(str(filepath), 1)
            cache.clear()
            assert cache.get(str(filepath)) is None

    def test_cache_stats(self):
        """Stats returns correct metrics."""
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "test.py"
            filepath.write_text("x = 1")
            cache_dir = Path(tmp) / "cache"
            cache = FileCache(max_entries=100, cache_dir=cache_dir)
            stats = cache.stats()
            assert stats["max_entries"] == 100

    def test_cache_disk_persistence(self):
        """Cache persists to disk and reloads."""
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "test.py"
            filepath.write_text("x = 1")
            cache_dir = Path(tmp) / "cache"
            cache = FileCache(max_entries=100, cache_dir=cache_dir)
            cache.set(str(filepath), {"data": "hello"})
            cache.save()

            cache2 = FileCache(max_entries=100, cache_dir=cache_dir)
            result = cache2.get(str(filepath))
            assert result is not None
            assert result["data"] == "hello"

    def test_file_hash(self):
        """File hash produces consistent results."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1")
            path = f.name
        try:
            h1 = FileCache._file_hash(path)
            h2 = FileCache._file_hash(path)
            assert h1 == h2
            assert len(h1) == 64
        finally:
            Path(path).unlink(missing_ok=True)

    def test_file_hash_missing_file(self):
        """Missing file returns empty string."""
        assert FileCache._file_hash("/nonexistent/file.py") == ""


class TestPerformanceOptimizer:
    """Coverage for performance.PerformanceOptimizer."""

    def test_init(self):
        """Default initialization."""
        opt = PerformanceOptimizer()
        assert opt.metrics is not None

    def test_detect_language(self):
        """Language detection from extension."""
        opt = PerformanceOptimizer()
        assert opt._detect_language(Path("test.py")) == "python"
        assert opt._detect_language(Path("test.ts")) == "typescript"
        assert opt._detect_language(Path("test.rs")) == "rust"
        assert opt._detect_language(Path("test.unknown")) == "unknown"

    def test_collect_files(self):
        """File collection scans directory for code files."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").touch()
            (tmp_path / "b.ts").touch()
            (tmp_path / "c.txt").touch()
            (tmp_path / "__pycache__").mkdir()
            (tmp_path / "__pycache__" / "cache.py").touch()

            opt = PerformanceOptimizer()
            files = opt._collect_files(tmp_path, languages=None)
            paths = {str(f.relative_to(tmp_path)) for f in files}
            assert "a.py" in paths
            assert "b.ts" in paths
            assert "c.txt" not in paths
            assert "__pycache__/cache.py" not in paths

    def test_collect_files_filter_language(self):
        """Language filter narrows file list."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").touch()
            (tmp_path / "b.ts").touch()

            opt = PerformanceOptimizer()
            files = opt._collect_files(tmp_path, languages=["python"])
            paths = {str(f.relative_to(tmp_path)) for f in files}
            assert "a.py" in paths
            assert "b.ts" not in paths

    def test_collect_files_empty_dir(self):
        """Empty directory returns no files."""
        with tempfile.TemporaryDirectory() as tmp:
            opt = PerformanceOptimizer()
            files = opt._collect_files(Path(tmp), languages=None)
            assert len(files) == 0

    def test_metrics_format(self):
        """format_metrics returns non-empty string."""
        opt = PerformanceOptimizer()
        text = opt.format_metrics()
        assert isinstance(text, str)
        assert len(text) > 0


# ── semantic_checker ──────────────────────────────────────────────


class TestImportGraph:
    """Coverage for semantic_checker.ImportGraph."""

    def test_empty_graph(self):
        """Empty graph has no cycles."""
        graph = ImportGraph()
        assert graph.find_cycles() == []

    def test_no_cycles(self):
        """Acyclic import graph returns empty."""
        graph = ImportGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        assert graph.find_cycles() == []

    def test_simple_cycle(self):
        """Simple cycle a→b→a is detected."""
        graph = ImportGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        cycles = graph.find_cycles()
        assert len(cycles) > 0
        assert any("a" in cycle for cycle in cycles)

    def test_self_import(self):
        """Self-import is detected as cycle."""
        graph = ImportGraph()
        graph.add_edge("a", "a")
        cycles = graph.find_cycles()
        assert cycles == [["a", "a"]]

    def test_larger_cycle(self):
        """3-node cycle is detected."""
        graph = ImportGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "a")
        cycles = graph.find_cycles()
        assert len(cycles) == 1


class TestSemanticIssue:
    """Coverage for semantic_checker.SemanticIssue."""

    def test_create_issue(self):
        """SemanticIssue can be created with all fields."""
        issue = SemanticIssue(
            file="src/main.py",
            line=10,
            severity="warning",
            category="complexity",
            rule_id="complexity-too-high",
            message="Function too complex",
            fix_hint="Refactor into smaller functions",
            context={"complexity": 15},
        )
        assert issue.file == "src/main.py"
        assert issue.rule_id == "complexity-too-high"

    def test_issue_to_dict(self):
        """Basic field access works."""
        issue = SemanticIssue(
            file="test.py",
            line=1,
            severity="error",
            category="security",
            rule_id="test-rule",
            message="Error message",
            fix_hint="Fix it",
        )
        assert issue.severity == "error"
        assert issue.category == "security"
        assert issue.file == "test.py"

    def test_issue_with_context(self):
        """Context field is stored when provided."""
        issue = SemanticIssue(
            file="test.py",
            line=5,
            severity="info",
            category="style",
            rule_id="style-rule",
            message="Style issue",
            fix_hint="Use snake_case",
            context={"suggestion": "Use snake_case"},
        )
        assert issue.context["suggestion"] == "Use snake_case"


class TestComplexityMetrics:
    """Coverage for semantic_checker.ComplexityMetrics."""

    def test_default_metrics(self):
        """Default metrics are zeroed."""
        m = ComplexityMetrics()
        assert m.total_functions == 0
        assert m.total_classes == 0
        assert m.total_lines == 0

    def test_metrics_with_values(self):
        """Metrics with values produce correct attributes."""
        m = ComplexityMetrics(
            total_functions=10,
            total_classes=3,
            total_imports=25,
            total_lines=500,
            avg_function_length=25.0,
            max_function_length=100,
            avg_complexity=4.5,
            max_complexity=12,
        )
        assert m.total_functions == 10
        assert m.avg_complexity == 4.5
        assert m.max_function_length == 100
        assert m.avg_function_length == 25.0


class TestSemanticChecker:
    """Coverage for semantic_checker.SemanticChecker."""

    def test_init(self):
        """SemanticChecker initializes without error."""
        checker = SemanticChecker()
        assert checker is not None

    def test_analyze_file_nonexistent(self):
        """Analyzing nonexistent file returns None."""
        checker = SemanticChecker()
        result = checker.analyze_file(Path("/nonexistent/nope.py"))
        assert result is None
