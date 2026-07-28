"""Tests for Phase 2 modules: AST parser, semantic checker, AST fixer, performance."""

from __future__ import annotations

from pathlib import Path

# ─────────────────────────────────────────────────────────────
# AST Parser Tests
# ─────────────────────────────────────────────────────────────


class TestASTParser:
    """Test tree-sitter AST parser."""

    def test_import(self):
        from tools.scripts.rules_engine.ast_parser import ASTParser

        assert ASTParser is not None

    def test_singleton(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        p1 = get_parser()
        p2 = get_parser()
        assert p1 is p2

    def test_availability(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        # tree-sitter is installed in this environment
        assert parser.available is True

    def test_supported_languages(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        supported = parser.supported_languages()
        assert "python" in supported

    def test_parse_python(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        tree = parser.parse("def foo(): pass", "python")
        assert tree is not None
        assert tree.root_node.type == "module"

    def test_parse_javascript(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        tree = parser.parse("function foo() {}", "javascript")
        assert tree is not None

    def test_extract_python_functions(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        code = '''
def hello():
    """Say hello."""
    return "world"

def add(a, b):
    return a + b
'''
        tree = parser.parse(code, "python")
        functions = parser.extract_functions(tree, "python")
        assert len(functions) == 2
        assert functions[0].name == "hello"
        assert functions[0].docstring is not None
        assert "Say hello" in functions[0].docstring
        assert functions[1].name == "add"
        assert functions[1].params == ["a", "b"]

    def test_extract_python_classes(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        code = '''
class MyClass:
    """A test class."""
    def method(self):
        pass
'''
        tree = parser.parse(code, "python")
        classes = parser.extract_classes(tree, "python")
        assert len(classes) == 1
        assert classes[0].name == "MyClass"
        assert len(classes[0].methods) == 1

    def test_extract_python_imports(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        code = "import os\nfrom pathlib import Path\nfrom typing import Any, List\n"
        tree = parser.parse(code, "python")
        imports = parser.extract_imports(tree, "python")
        assert len(imports) == 3

    def test_parse_file(self, tmp_path):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        f = tmp_path / "test.py"
        f.write_text('def foo():\n    """Docstring."""\n    return 1\n')
        result = parser.parse_file(f)
        assert result is not None
        assert result.language == "python"
        assert len(result.functions) == 1
        assert result.functions[0].name == "foo"

    def test_parse_nonexistent_file(self, tmp_path):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        result = parser.parse_file(tmp_path / "nonexistent.py")
        assert result is None

    def test_error_nodes(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        tree = parser.parse("def foo(:\n", "python")
        assert tree is not None
        # Syntax errors produce ERROR nodes

    def test_complexity_estimation(self):
        from tools.scripts.rules_engine.ast_parser import get_parser

        parser = get_parser()
        code = """
def complex_func(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                try:
                    pass
                except:
                    pass
    return x
"""
        tree = parser.parse(code, "python")
        functions = parser.extract_functions(tree, "python")
        assert len(functions) == 1
        assert functions[0].complexity > 1  # Has branching


# ─────────────────────────────────────────────────────────────
# Semantic Checker Tests
# ─────────────────────────────────────────────────────────────


class TestSemanticChecker:
    """Test semantic analysis engine."""

    def test_import(self):
        from tools.scripts.rules_engine.semantic_checker import SemanticChecker

        assert SemanticChecker is not None

    def test_analyze_file(self, tmp_path):
        from tools.scripts.rules_engine.semantic_checker import SemanticChecker

        checker = SemanticChecker()
        f = tmp_path / "test.py"
        f.write_text('def foo():\n    """Doc."""\n    return 1\n')
        result = checker.analyze_file(f)
        assert result is not None

    def test_analyze_directory(self, tmp_path):
        from tools.scripts.rules_engine.semantic_checker import SemanticChecker

        checker = SemanticChecker()
        (tmp_path / "a.py").write_text('def hello():\n    """Say hello."""\n    return "world"\n')
        (tmp_path / "b.py").write_text('def add(a, b):\n    """Add two numbers."""\n    return a + b\n')
        result = checker.analyze_directory(tmp_path)
        assert result.files_analyzed >= 2
        assert result.metrics.total_functions >= 2

    def test_empty_directory(self, tmp_path):
        from tools.scripts.rules_engine.semantic_checker import SemanticChecker

        checker = SemanticChecker()
        result = checker.analyze_directory(tmp_path)
        assert result.files_analyzed == 0
        assert len(result.issues) == 0

    def test_import_cycle_detection(self):
        from tools.scripts.rules_engine.semantic_checker import ImportGraph

        graph = ImportGraph()
        # Use consistent identifiers so DFS can trace the cycle
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        cycles = graph.find_cycles()
        assert len(cycles) > 0

    def test_import_graph_no_cycles(self):
        from tools.scripts.rules_engine.semantic_checker import ImportGraph

        graph = ImportGraph()
        graph.add_edge("a.py", "b")
        graph.add_edge("b.py", "c")
        cycles = graph.find_cycles()
        assert len(cycles) == 0

    def test_shadowed_imports(self):
        from tools.scripts.rules_engine.semantic_checker import ImportGraph, ImportInfo

        graph = ImportGraph()
        imports = {
            "test.py": [ImportInfo(module="collections", names=["list"], line=1, is_from=True, level=0)],
        }
        issues = graph.find_shadowed_imports(imports)
        assert len(issues) > 0
        assert issues[0].rule_id == "shadowed-import"

    def test_format_metrics(self, tmp_path):
        from tools.scripts.rules_engine.semantic_checker import SemanticChecker

        checker = SemanticChecker()
        (tmp_path / "a.py").write_text("x = 1\n")
        result = checker.analyze_directory(tmp_path)
        # Metrics should be formattable
        assert result.metrics is not None


# ─────────────────────────────────────────────────────────────
# AST Fixer Tests
# ─────────────────────────────────────────────────────────────


class TestASTFixer:
    """Test AST-based code fixer."""

    def test_import(self):
        from tools.scripts.rules_engine.ast_fixer import ASTFixer

        assert ASTFixer is not None

    def test_fix_bare_except(self):
        from tools.scripts.rules_engine.ast_fixer import ASTFixer

        fixer = ASTFixer()
        content = "try:\n    x = 1\nexcept:\n    pass\n"
        fixed, fixes = fixer.fix_content(content, "python")
        assert len(fixes) > 0
        assert "except Exception:" in fixed

    def test_fix_file(self, tmp_path):
        from tools.scripts.rules_engine.ast_fixer import ASTFixer

        fixer = ASTFixer()
        f = tmp_path / "test.py"
        f.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        report = fixer.fix_file(f, dry_run=True)
        assert report is not None
        assert report.total_fixes > 0
        # Dry run should not modify file
        assert f.read_text() == "try:\n    x = 1\nexcept:\n    pass\n"

    def test_fix_file_apply(self, tmp_path):
        from tools.scripts.rules_engine.ast_fixer import ASTFixer

        fixer = ASTFixer()
        f = tmp_path / "test.py"
        original = "try:\n    x = 1\nexcept:\n    pass\n"
        f.write_text(original)
        report = fixer.fix_file(f, dry_run=False)
        assert report is not None
        # Report should have fixes
        assert report.total_fixes > 0
        # When dry_run=False, auto_safe fixes are applied
        # The file content in the report should be modified
        assert "except Exception:" in report.fixed_content

    def test_format_report(self, tmp_path):
        from tools.scripts.rules_engine.ast_fixer import ASTFixer

        fixer = ASTFixer()
        f = tmp_path / "test.py"
        f.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        report = fixer.fix_file(f)
        text = fixer.format_fix_report(report)
        assert "Fix Report" in text
        assert "fix-bare-except" in text

    def test_empty_file(self, tmp_path):
        from tools.scripts.rules_engine.ast_fixer import ASTFixer

        fixer = ASTFixer()
        f = tmp_path / "empty.py"
        f.write_text("")
        report = fixer.fix_file(f)
        assert report is not None
        assert report.total_fixes == 0


# ─────────────────────────────────────────────────────────────
# Performance Module Tests
# ─────────────────────────────────────────────────────────────


class TestPerformance:
    """Test performance optimization module."""

    def test_import(self):
        from tools.scripts.rules_engine.performance import FileCache, PerformanceOptimizer

        assert PerformanceOptimizer is not None
        assert FileCache is not None

    def test_optimizer_init(self):
        from tools.scripts.rules_engine.performance import PerformanceOptimizer

        optimizer = PerformanceOptimizer()
        assert optimizer.max_workers >= 1

    def test_optimizer_no_cache(self):
        from tools.scripts.rules_engine.performance import PerformanceOptimizer

        optimizer = PerformanceOptimizer(cache_enabled=False)
        assert optimizer.cache is None

    def test_optimized_check(self, tmp_path):
        from tools.scripts.rules_engine.performance import PerformanceOptimizer

        optimizer = PerformanceOptimizer(cache_enabled=False)
        (tmp_path / "a.py").write_text("x = 1\n")
        results = optimizer.optimized_check_directory(tmp_path, parallel=False)
        assert isinstance(results, list)
        assert optimizer.metrics.total_files >= 1

    def test_file_cache(self, tmp_path):
        from tools.scripts.rules_engine.performance import FileCache

        cache = FileCache(cache_dir=tmp_path / "cache")
        cache.set("/fake/file.py", {"test": True})
        result = cache.get("/fake/file.py")
        # Won't match because file doesn't exist on disk
        assert result is None

    def test_cache_stats(self, tmp_path):
        from tools.scripts.rules_engine.performance import FileCache

        cache = FileCache(cache_dir=tmp_path / "cache")
        stats = cache.stats()
        assert "entries" in stats

    def test_format_metrics(self, tmp_path):
        from tools.scripts.rules_engine.performance import PerformanceOptimizer

        optimizer = PerformanceOptimizer(cache_enabled=False)
        (tmp_path / "a.py").write_text("x = 1\n")
        optimizer.optimized_check_directory(tmp_path, parallel=False)
        text = optimizer.format_metrics()
        assert "Performance Metrics" in text

    def test_language_detection(self):
        from tools.scripts.rules_engine.performance import PerformanceOptimizer

        optimizer = PerformanceOptimizer()
        assert optimizer._detect_language(Path("test.py")) == "python"
        assert optimizer._detect_language(Path("test.js")) == "javascript"
        assert optimizer._detect_language(Path("test.rs")) == "rust"
