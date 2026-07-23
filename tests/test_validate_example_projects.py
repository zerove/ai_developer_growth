#!/usr/bin/env python3
"""
validate_example_projects.py 测试
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestValidateExampleProjects:
    """validate_example_projects.py 测试"""

    def _run(self, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "tools/scripts/validate_example_projects.py"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
            **kwargs,
        )

    def test_main_passes(self):
        """所有 example 通过验证"""
        result = self._run()
        assert result.returncode == 0
        assert "10 通过" in result.stdout

    def test_main_shows_all_examples(self):
        """输出包含所有 example 名称"""
        result = self._run()
        for name in ["ai-context-sync", "ai-growth-slack", "ai-navigation", "multi-agent-orch", "self-correction-loop"]:
            assert name in result.stdout

    def test_validate_example_valid(self, tmp_path):
        """有效 example 通过验证"""
        from tools.scripts.validate_example_projects import validate_example

        example_dir = tmp_path / "good-example"
        example_dir.mkdir()
        (example_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        (example_dir / "README.md").write_text("# Test")
        (example_dir / "tests").mkdir()
        (example_dir / "tests" / "__init__.py").write_text("")
        (example_dir / "main.py").write_text("x = 1\n")

        issues = validate_example(example_dir)
        assert len(issues) == 0

    def test_validate_example_missing_pyproject(self, tmp_path):
        """缺少 pyproject.toml"""
        from tools.scripts.validate_example_projects import validate_example

        example_dir = tmp_path / "bad-example"
        example_dir.mkdir()
        (example_dir / "README.md").write_text("# Test")
        (example_dir / "tests").mkdir()
        (example_dir / "main.py").write_text("x = 1\n")

        issues = validate_example(example_dir)
        assert any("pyproject.toml" in i for i in issues)

    def test_validate_example_missing_readme(self, tmp_path):
        """缺少 README.md"""
        from tools.scripts.validate_example_projects import validate_example

        example_dir = tmp_path / "no-readme"
        example_dir.mkdir()
        (example_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        (example_dir / "tests").mkdir()
        (example_dir / "main.py").write_text("x = 1\n")

        issues = validate_example(example_dir)
        assert any("README.md" in i for i in issues)

    def test_validate_example_missing_tests(self, tmp_path):
        """缺少 tests/ 目录"""
        from tools.scripts.validate_example_projects import validate_example

        example_dir = tmp_path / "no-tests"
        example_dir.mkdir()
        (example_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        (example_dir / "README.md").write_text("# Test")
        (example_dir / "main.py").write_text("x = 1\n")

        issues = validate_example(example_dir)
        assert any("tests" in i for i in issues)

    def test_validate_example_no_python(self, tmp_path):
        """没有 Python 文件"""
        from tools.scripts.validate_example_projects import validate_example

        example_dir = tmp_path / "no-python"
        example_dir.mkdir()
        (example_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        (example_dir / "README.md").write_text("# Test")
        (example_dir / "tests").mkdir()

        issues = validate_example(example_dir)
        assert any("Python" in i for i in issues)

    def test_validate_example_bad_pyproject(self, tmp_path):
        """pyproject.toml 缺少 name"""
        from tools.scripts.validate_example_projects import validate_example

        example_dir = tmp_path / "bad-pyproject"
        example_dir.mkdir()
        (example_dir / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
        (example_dir / "README.md").write_text("# Test")
        (example_dir / "tests").mkdir()
        (example_dir / "main.py").write_text("x = 1\n")

        issues = validate_example(example_dir)
        assert any("name" in i for i in issues)
