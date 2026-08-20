#!/usr/bin/env python3
"""
Tests for detect_language.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.scripts.detect_language import (
    count_extensions,
    detect_language,
    detect_language_from_file,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestExtensionDetection:
    def test_python(self):
        assert detect_language_from_file(Path("main.py")) == "python"
        assert detect_language_from_file(Path("utils.pyi")) == "python"

    def test_typescript(self):
        assert detect_language_from_file(Path("app.ts")) == "typescript"
        assert detect_language_from_file(Path("page.tsx")) == "typescript"

    def test_javascript(self):
        assert detect_language_from_file(Path("script.js")) == "javascript"
        assert detect_language_from_file(Path("component.jsx")) == "javascript"

    def test_rust(self):
        assert detect_language_from_file(Path("main.rs")) == "rust"

    def test_go(self):
        assert detect_language_from_file(Path("main.go")) == "go"

    def test_java(self):
        assert detect_language_from_file(Path("App.java")) == "java"

    def test_unknown(self):
        assert detect_language_from_file(Path("data.xyz")) is None


class TestCountExtensions:
    def test_counts_files(self, tmp_dir):
        (tmp_dir / "a.py").write_text("")
        (tmp_dir / "b.py").write_text("")
        (tmp_dir / "c.ts").write_text("")
        counts = count_extensions(tmp_dir)
        assert counts["python"] == 2
        assert counts["typescript"] == 1

    def test_skips_ignored_dirs(self, tmp_dir):
        (tmp_dir / "app.py").write_text("")
        node_modules = tmp_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "dep.js").write_text("")
        counts = count_extensions(tmp_dir)
        assert counts.get("javascript", 0) == 0
        assert counts["python"] == 1


class TestDetectLanguage:
    def test_python_project(self, tmp_dir):
        (tmp_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        result = detect_language(tmp_dir)
        assert result["language"] == "python"
        assert result["confidence"] >= 0.9

    def test_rust_project(self, tmp_dir):
        (tmp_dir / "Cargo.toml").write_text("[package]\nname = 'test'")
        result = detect_language(tmp_dir)
        assert result["language"] == "rust"
        assert result["confidence"] >= 0.9

    def test_go_project(self, tmp_dir):
        (tmp_dir / "go.mod").write_text("module test")
        result = detect_language(tmp_dir)
        assert result["language"] == "go"
        assert result["confidence"] >= 0.9

    def test_typescript_project(self, tmp_dir):
        (tmp_dir / "tsconfig.json").write_text("{}")
        (tmp_dir / "package.json").write_text('{"dependencies": {}}')
        result = detect_language(tmp_dir)
        assert result["language"] == "typescript"
        assert result["confidence"] >= 0.9

    def test_fallback_to_extensions(self, tmp_dir):
        (tmp_dir / "a.py").write_text("")
        (tmp_dir / "b.py").write_text("")
        (tmp_dir / "c.py").write_text("")
        result = detect_language(tmp_dir)
        assert result["language"] == "python"
        assert result["confidence"] > 0.5

    def test_empty_directory(self, tmp_dir):
        result = detect_language(tmp_dir)
        assert result["language"] == "unknown"
        assert result["confidence"] == 0.0

    def test_framework_detection_react(self, tmp_dir):
        (tmp_dir / "package.json").write_text(
            '{"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}'
        )
        (tmp_dir / "tsconfig.json").write_text("{}")
        result = detect_language(tmp_dir)
        assert result["framework"] in ("react", "nextjs")

    def test_framework_detection_django(self, tmp_dir):
        (tmp_dir / "requirements.txt").write_text("django==4.2\n")
        result = detect_language(tmp_dir)
        assert result["framework"] == "django"

    def test_framework_detection_fastapi(self, tmp_dir):
        (tmp_dir / "requirements.txt").write_text("fastapi==0.100.0\n")
        result = detect_language(tmp_dir)
        assert result["framework"] == "fastapi"


class TestCLI:
    def test_main_no_args(self, tmp_dir):
        """Test main() with default args."""
        import sys

        from tools.scripts.detect_language import main

        old_argv = sys.argv
        sys.argv = ["detect_language", str(tmp_dir)]
        try:
            assert main() == 0
        finally:
            sys.argv = old_argv

    def test_main_json_output(self, tmp_dir):
        """Test main() with --json flag."""
        import sys

        from tools.scripts.detect_language import main

        old_argv = sys.argv
        sys.argv = ["detect_language", str(tmp_dir), "--json"]
        try:
            assert main() == 0
        finally:
            sys.argv = old_argv

    def test_main_not_a_dir(self, tmp_path):
        """Test main() with a non-directory path."""
        import sys

        from tools.scripts.detect_language import main

        old_argv = sys.argv
        sys.argv = ["detect_language", str(tmp_path / "nonexistent")]
        try:
            assert main() == 1
        finally:
            sys.argv = old_argv


class TestGoMod:
    def test_go_mod_with_framework(self, tmp_dir):
        """Test go.mod framework detection."""
        from tools.scripts.detect_language import detect_framework_from_go_mod

        (tmp_dir / "go.mod").write_text('require "github.com/gin-gonic/gin" v1.9.0')
        assert detect_framework_from_go_mod(tmp_dir) == "gin"

    def test_go_mod_no_framework(self, tmp_dir):
        """Test go.mod without known framework."""
        from tools.scripts.detect_language import detect_framework_from_go_mod

        (tmp_dir / "go.mod").write_text("module myproject\n")
        assert detect_framework_from_go_mod(tmp_dir) is None

    def test_go_mod_no_file(self, tmp_dir):
        """Test go.mod detection when file doesn't exist."""
        from tools.scripts.detect_language import detect_framework_from_go_mod

        assert detect_framework_from_go_mod(tmp_dir) is None


class TestFrameworkDetection:
    def test_framework_for_python(self, tmp_dir):
        """Test framework detection for Python."""
        from tools.scripts.detect_language import detect_framework

        (tmp_dir / "requirements.txt").write_text("django==4.2\n")
        assert detect_framework(tmp_dir, "python") == "django"

    def test_framework_for_go(self, tmp_dir):
        """Test framework detection for Go."""
        from tools.scripts.detect_language import detect_framework

        (tmp_dir / "go.mod").write_text('require "github.com/gin-gonic/gin" v1.9.0')
        assert detect_framework(tmp_dir, "go") == "gin"

    def test_framework_for_unknown_lang(self, tmp_dir):
        """Test framework detection for unsupported language."""
        from tools.scripts.detect_language import detect_framework

        assert detect_framework(tmp_dir, "fortran") is None

    def test_framework_from_requirements_no_match(self, tmp_dir):
        """Test requirements.txt with no known framework."""
        from tools.scripts.detect_language import detect_framework_from_requirements

        (tmp_dir / "requirements.txt").write_text("numpy==1.24\n")
        assert detect_framework_from_requirements(tmp_dir) is None
