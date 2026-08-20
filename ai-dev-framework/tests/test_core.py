#!/usr/bin/env python3
"""Tests for ai-dev-framework core modules."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_dev_framework.hook_system import Hook, HookConfig, create_default_config
from ai_dev_framework.project_config import JcodeConfig, ProjectConfig, init_project


class TestProjectConfig:
    """Test ProjectConfig dataclass."""

    def test_create_config(self):
        """Test creating a project config."""
        config = ProjectConfig(name="test-project", type="library", language="python")
        assert config.name == "test-project"
        assert config.type == "library"
        assert config.language == "python"
        assert config.min_test_coverage == 70

    def test_config_defaults(self):
        """Test config default values."""
        config = ProjectConfig(name="test", type="lib", language="py")
        assert config.source_dir == "src"
        assert config.tests_dir == "tests"
        assert config.docs_dir == "docs"
        assert config.lint_tool == "ruff"


class TestJcodeConfig:
    """Test JcodeConfig class."""

    def test_create_config(self):
        """Test creating a jcode config."""
        project = ProjectConfig(name="test", type="lib", language="py")
        config = JcodeConfig(project=project)
        assert config.project.name == "test"
        assert len(config.agents) == 0

    def test_save_and_load_json(self):
        """Test saving and loading JSON config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = ProjectConfig(name="test", type="lib", language="py")
            config = JcodeConfig(project=project)

            # Save
            config_path = Path(tmpdir) / "jcode.json"
            config.save(str(config_path))
            assert config_path.exists()

            # Load
            loaded = JcodeConfig.load(str(config_path))
            assert loaded.project.name == "test"

    def test_to_dict(self):
        """Test converting to dict."""
        project = ProjectConfig(name="test", type="lib", language="py")
        config = JcodeConfig(project=project)

        data = config.to_dict()
        assert data["project"]["name"] == "test"
        assert data["project"]["language"] == "py"


class TestInitProject:
    """Test init_project function."""

    def test_init_python_project(self):
        """Test initializing a Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = init_project(
                project_name="my-lib",
                project_type="library",
                language="python",
                output_dir=tmpdir,
            )

            assert config.project.name == "my-lib"
            assert config.project.language == "python"
            assert config.project.lint_tool == "ruff"

            # Check files created
            assert (Path(tmpdir) / "jcode.yaml").exists()
            assert (Path(tmpdir) / ".jcode" / "PROJECT.md").exists()

    def test_init_typescript_project(self):
        """Test initializing a TypeScript project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = init_project(
                project_name="my-app",
                project_type="webapp",
                language="typescript",
                output_dir=tmpdir,
            )

            assert config.project.lint_tool == "eslint"
            assert config.project.type_checker == "tsc"


class TestHook:
    """Test Hook dataclass."""

    def test_create_hook(self):
        """Test creating a hook."""
        hook = Hook(
            name="lint-check",
            agent="code-guardian",
            action="lint",
            description="Check code style",
        )
        assert hook.name == "lint-check"
        assert hook.enabled is True


class TestHookConfig:
    """Test HookConfig class."""

    def test_create_config(self):
        """Test creating a hook config."""
        config = HookConfig()
        assert len(config.on_commit) == 0

    def test_save_and_load(self):
        """Test saving and loading hook config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = create_default_config("python")

            # Save
            config_path = Path(tmpdir) / "hooks.json"
            config.save(str(config_path))
            assert config_path.exists()

            # Load
            loaded = HookConfig.load(str(config_path))
            assert len(loaded.on_commit) > 0
            assert len(loaded.on_pr) > 0


class TestCreateDefaultConfig:
    """Test create_default_config function."""

    def test_generic_config(self):
        """Test creating generic config."""
        config = create_default_config("generic")
        assert len(config.on_commit) > 0
        assert len(config.on_pr) > 0

    def test_python_config(self):
        """Test creating Python-specific config."""
        config = create_default_config("python")
        # Should have pytest hook
        pytest_hooks = [h for h in config.on_commit if "pytest" in h.name]
        assert len(pytest_hooks) > 0

    def test_typescript_config(self):
        """Test creating TypeScript-specific config."""
        config = create_default_config("typescript")
        # Should have vitest hook
        vitest_hooks = [h for h in config.on_commit if "vitest" in h.name]
        assert len(vitest_hooks) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
