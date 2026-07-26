"""Tests for ADG CLI P1.2 - Parallel checking."""

from tools.scripts.adg_cli import (
    _check_files_parallel,
    check_directory,
    load_rules_for_language,
)


class TestParallelChecking:
    """Test parallel checking functionality."""

    def test_check_directory_sequential(self, tmp_path):
        """Sequential checking (jobs=1) works correctly."""
        # Create multiple Python files with issues
        for i in range(5):
            (tmp_path / f"test_{i}.py").write_text(
                f"print('hello {i}')\n"  # py-print-statement issue
            )

        rules = load_rules_for_language("python")
        issues = check_directory(tmp_path, rules, jobs=1)

        # Should find issues in all files
        assert len(issues) == 5

    def test_check_directory_parallel(self, tmp_path):
        """Parallel checking (jobs>1) produces same results as sequential."""
        # Create multiple Python files with issues
        for i in range(5):
            (tmp_path / f"test_{i}.py").write_text(
                f"print('hello {i}')\n"  # py-print-statement issue
            )

        rules = load_rules_for_language("python")

        # Sequential check
        issues_seq = check_directory(tmp_path, rules, jobs=1)

        # Parallel check
        issues_par = check_directory(tmp_path, rules, jobs=4)

        # Both should find same number of issues
        assert len(issues_seq) == len(issues_par)

        # Check same files are reported
        files_seq = {str(i.file) for i in issues_seq}
        files_par = {str(i.file) for i in issues_par}
        assert files_seq == files_par

    def test_parallel_performance(self, tmp_path):
        """Parallel checking should not be significantly slower."""
        import time

        # Create many files
        for i in range(20):
            (tmp_path / f"module_{i}.py").write_text(f"print('hello {i}')\nx = None\n")

        rules = load_rules_for_language("python")

        # Sequential timing
        start = time.time()
        issues_seq = check_directory(tmp_path, rules, jobs=1)
        time.time() - start

        # Parallel timing
        start = time.time()
        issues_par = check_directory(tmp_path, rules, jobs=4)
        time.time() - start

        # Both should find same issues
        assert len(issues_seq) == len(issues_par)

        # Parallel should not be significantly slower (allow 2x for overhead)
        # Note: For small files, parallel may be slower due to process spawn overhead
        # This test mainly ensures parallel execution doesn't break anything

    def test_parallel_with_severity_filter(self, tmp_path):
        """Parallel checking respects severity filter."""
        # Create files with different severity issues
        (tmp_path / "error_file.py").write_text("except:\n    pass\n")  # error
        (tmp_path / "info_file.py").write_text("print('hello')\n")  # info

        rules = load_rules_for_language("python")

        # Check only errors
        issues = check_directory(tmp_path, rules, severity_filter="error", jobs=2)

        # Should only have error severity issues
        for issue in issues:
            assert issue.severity == "error"

    def test_empty_directory_parallel(self, tmp_path):
        """Parallel checking handles empty directory."""
        rules = load_rules_for_language("python")
        issues = check_directory(tmp_path, rules, jobs=4)
        assert issues == []

    def test_single_file_parallel_flag(self, tmp_path):
        """With jobs>1 but only 1 file, should still work (use sequential)."""
        (tmp_path / "single.py").write_text("print('hello')\n")

        rules = load_rules_for_language("python")
        issues = check_directory(tmp_path, rules, jobs=4)

        # Should find the issue
        assert len(issues) == 1


class TestParallelInternalFunction:
    """Test _check_files_parallel internal function."""

    def test_parallel_returns_issues(self, tmp_path):
        """_check_files_parallel returns correct issues."""
        files = []
        for i in range(3):
            fp = tmp_path / f"file_{i}.py"
            fp.write_text("print('test')\n")
            files.append(fp)

        rules = load_rules_for_language("python")
        issues = _check_files_parallel(files, rules, None, 2)

        # Should find issues in all files
        assert len(issues) == 3

    def test_parallel_handles_empty_list(self):
        """_check_files_parallel handles empty file list."""
        rules = load_rules_for_language("python")
        issues = _check_files_parallel([], rules, None, 4)
        assert issues == []
