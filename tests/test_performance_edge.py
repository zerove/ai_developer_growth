"""Targeted tests for performance.py remaining uncovered paths (_get_memory_usage, parallel error)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tools.scripts.rules_engine.performance import PerformanceOptimizer


class TestPerformanceEdgeCases:
    """Cover remaining 11% of performance.py."""

    def test_get_memory_usage(self):
        """_get_memory_usage returns a non-negative number."""
        opt = PerformanceOptimizer()
        mem = opt._get_memory_usage()
        assert isinstance(mem, int | float)
        assert mem >= 0

    def test_parallel_check_with_exception(self):
        """Parallel check gracefully handles worker exceptions."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(5):
                (tmp_path / f"f{i}.py").write_text(f"x = {i}")

            opt = PerformanceOptimizer(max_workers=2, cache_enabled=False)
            # Provide a non-existent worker - triggers exception handling
            files = [(str(tmp_path / f"f{i}.py"), "python") for i in range(5)]
            # Add one bad entry to trigger exception
            files.append(("/nonexistent/file.py", "python"))
            results = opt._parallel_check(files)
            assert results is not None
            # At least some results should be valid (non-None)
            valid = [r for r in results if r is not None]
            assert len(valid) >= 5

    def test_serial_check_empty(self):
        """Serial check of empty list returns empty list."""
        opt = PerformanceOptimizer()
        results = opt._serial_check([])
        assert results == []

    def test_serial_check_with_results(self):
        """Serial check processes files one by one."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")
            (tmp_path / "b.py").write_text("y = 2")

            opt = PerformanceOptimizer()
            files = [
                (str(tmp_path / "a.py"), "python"),
                (str(tmp_path / "b.py"), "python"),
            ]
            results = opt._serial_check(files)
            assert results is not None
            assert len(results) == 2

    def test_format_metrics_with_data(self):
        """format_metrics returns report after analysis."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")

            opt = PerformanceOptimizer()
            opt.optimized_check_directory(tmp_path)
            text = opt.format_metrics()
            assert "Performance Metrics" in text
            assert "Files" in text or "files" in text.lower()

    def test_metrics_property(self):
        """metrics property returns a PerformanceMetrics object."""
        opt = PerformanceOptimizer()
        m = opt.metrics
        # Check known attributes from PerformanceMetrics
        assert hasattr(m, "total_files") or hasattr(m, "avg_ms_per_file")
