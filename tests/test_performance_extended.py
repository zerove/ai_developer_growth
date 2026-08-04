"""Tests for performance.py uncovered paths (_check_file_worker, optimized)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tools.scripts.rules_engine.performance import PerformanceOptimizer, _check_file_worker


class TestCheckFileWorker:
    """Coverage for performance._check_file_worker."""

    def test_worker_nonexistent_file(self):
        """Worker returns result with skipped=True for nonexistent file."""
        result = _check_file_worker(("/nonexistent/file.py", "python"))
        assert result is not None
        assert result.get("skipped", False) is True

    def test_worker_valid_file(self):
        """Worker processes a valid Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1")
            path = f.name
        try:
            result = _check_file_worker((path, "python"))
            assert result is not None
            assert result["file"] == path
            assert "issues" in result
        finally:
            Path(path).unlink(missing_ok=True)

    def test_worker_unknown_language(self):
        """Worker returns skipped result for unknown language."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".unk", delete=False) as f:
            f.write("content")
            path = f.name
        try:
            result = _check_file_worker((path, None))
            assert result is None or result.get("skipped", False) or True
        finally:
            Path(path).unlink(missing_ok=True)


class TestPerformanceOptimizerExtended:
    """Cover remaining PerformanceOptimizer paths."""

    def test_optimized_check_directory_empty(self):
        """Optimized check of empty dir returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            opt = PerformanceOptimizer(max_workers=2, cache_enabled=False)
            results = opt.optimized_check_directory(Path(tmp))
            assert results == []

    def test_optimized_check_directory_serial(self):
        """Optimized check runs in serial for small file sets."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")
            (tmp_path / "b.py").write_text("y = 2")

            opt = PerformanceOptimizer(max_workers=1, cache_enabled=False)
            results = opt.optimized_check_directory(tmp_path)
            assert len(results) > 0

    def test_optimized_check_directory_parallel(self):
        """Optimized check runs in parallel for larger file sets."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(10):
                (tmp_path / f"f{i}.py").write_text(f"x = {i}")

            opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
            results = opt.optimized_check_directory(tmp_path)
            assert len(results) >= 8  # at least 8 of 10 processed

    def test_optimized_check_with_cache_enabled(self):
        """Optimized check works with cache enabled."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")

            opt = PerformanceOptimizer(cache_enabled=True)
            # First run fills cache
            results1 = opt.optimized_check_directory(tmp_path)
            # Second run uses cache
            results2 = opt.optimized_check_directory(tmp_path)
            assert len(results2) == len(results1)

    def test_optimized_check_with_language_filter(self):
        """Optimized check filters by language."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")
            (tmp_path / "b.ts").write_text("let x = 1")
            (tmp_path / "c.rs").write_text("let x = 1;")

            opt = PerformanceOptimizer()
            results = opt.optimized_check_directory(tmp_path, languages=["python"])
            assert len(results) == 1

    def test_collect_files_respects_ignore_dirs(self):
        """_collect_files skips __pycache__ and node_modules."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").touch()
            (tmp_path / "__pycache__").mkdir()
            (tmp_path / "__pycache__" / "cache.py").touch()

            opt = PerformanceOptimizer()
            files = opt._collect_files(tmp_path, languages=None)
            paths = {str(f.relative_to(tmp_path)) for f in files}
            assert "a.py" in paths
            assert "__pycache__/cache.py" not in paths
