"""Tests for validate_example_projects.py (48% → target 85%)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.validate_example_projects import (
    MIN_PYTHON_FILES,
    REQUIRED_DIRS,
    REQUIRED_FILES,
    main,
    validate_example,
)


class TestValidateExample:
    """Tests for validate_example()."""

    def test_perfect_example(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "1.0"\n'
        )
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        (tmp_path / "main.py").write_text("pass")
        assert validate_example(tmp_path) == []

    def test_missing_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        (tmp_path / "main.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("pyproject.toml" in i for i in issues)

    def test_missing_readme(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1"\n'
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "main.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("README.md" in i for i in issues)

    def test_missing_tests_dir(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1"\n'
        )
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "main.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("tests/" in i for i in issues)

    def test_no_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1"\n'
        )
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        issues = validate_example(tmp_path)
        assert any("Python 文件不足" in i for i in issues)

    def test_pyproject_missing_name(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1"\n')
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        (tmp_path / "main.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("name" in i for i in issues)

    def test_pyproject_missing_version(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        (tmp_path / "main.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("version" in i for i in issues)

    def test_python_files_under_pycache_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1"\n'
        )
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        # Only __pycache__ python files
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("Python 文件不足" in i for i in issues)

    def test_all_missing(self, tmp_path: Path) -> None:
        issues = validate_example(tmp_path)
        assert len(issues) >= 3  # missing files + dir + python

    def test_pyproject_exists_but_empty(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "tests").mkdir()
        (tmp_path / "main.py").write_text("pass")
        issues = validate_example(tmp_path)
        assert any("name" in i for i in issues)


class TestMain:
    """Tests for main() function."""

    def test_no_examples_dir(self, tmp_path: Path) -> None:
        """When examples/ doesn't exist, main() exits 1."""
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        finally:
            os.chdir(old_cwd)

    def test_all_pass(self, tmp_path: Path) -> None:
        import os

        old_cwd = os.getcwd()
        try:
            examples_dir = tmp_path / "examples"
            examples_dir.mkdir()
            ex = examples_dir / "good-example"
            ex.mkdir()
            (ex / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1"\n')
            (ex / "README.md").write_text("# Test")
            (ex / "tests").mkdir()
            (ex / "main.py").write_text("pass")
            os.chdir(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            os.chdir(old_cwd)

    def test_some_fail(self, tmp_path: Path) -> None:
        import os

        old_cwd = os.getcwd()
        try:
            examples_dir = tmp_path / "examples"
            examples_dir.mkdir()
            bad = examples_dir / "bad"
            bad.mkdir()
            good = examples_dir / "good"
            good.mkdir()
            (good / "pyproject.toml").write_text(
                '[project]\nname = "x"\nversion = "1"\n'
            )
            (good / "README.md").write_text("# Test")
            (good / "tests").mkdir()
            (good / "main.py").write_text("pass")
            os.chdir(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        finally:
            os.chdir(old_cwd)

    def test_skip_non_dir_entries(self, tmp_path: Path) -> None:
        import os

        old_cwd = os.getcwd()
        try:
            examples_dir = tmp_path / "examples"
            examples_dir.mkdir()
            (examples_dir / "file.txt").write_text("not a dir")
            os.chdir(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            os.chdir(old_cwd)


class TestConstants:
    """Tests for module constants."""

    def test_required_files(self) -> None:
        assert "pyproject.toml" in REQUIRED_FILES
        assert "README.md" in REQUIRED_FILES

    def test_required_dirs(self) -> None:
        assert "tests" in REQUIRED_DIRS

    def test_min_python_files(self) -> None:
        assert MIN_PYTHON_FILES >= 1
