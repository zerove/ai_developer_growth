"""Tests for ai_rules_generator.py module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.scripts.rules_engine.ai_rules_generator import (
    PATTERN_DETECTORS,
    analyze_project,
    detect_language_from_files,
    format_analysis,
)


class TestDetectLanguageFromFiles:
    """Test language detection from file list."""

    def test_python_project(self):
        files = [Path("a.py"), Path("b.py"), Path("c.py")]
        assert detect_language_from_files(files) == "python"

    def test_js_project(self):
        files = [Path("a.js"), Path("b.ts"), Path("c.jsx")]
        assert detect_language_from_files(files) == "javascript"

    def test_mixed_project(self):
        files = [Path("a.py"), Path("b.py"), Path("c.js")]
        assert detect_language_from_files(files) == "python"

    def test_no_code_files(self):
        files = [Path("README.md"), Path("LICENSE")]
        assert detect_language_from_files(files) == "unknown"

    def test_empty_list(self):
        assert detect_language_from_files([]) == "unknown"


class TestAnalyzeProject:
    """Test project analysis."""

    def test_empty_project(self, tmp_path):
        result = analyze_project(tmp_path)
        assert "error" in result

    def test_python_project(self, tmp_path):
        (tmp_path / "main.py").write_text('import os\nprint("hello")\neval("x")\n')
        (tmp_path / "utils.py").write_text("def foo():\n    TODO: fix this\n    pass\n")
        result = analyze_project(tmp_path)
        assert result["language"] == "python"
        assert result["files_analyzed"] == 2
        assert result["detected_patterns"] > 0

    def test_patterns_detected(self, tmp_path):
        (tmp_path / "app.py").write_text("eval(user_input)\n")
        result = analyze_project(tmp_path)
        pattern_ids = [p["id"] for p in result["rules"]["anti_patterns"]]
        assert "detected-eval-usage" in pattern_ids

    def test_empty_catch_detected(self, tmp_path):
        (tmp_path / "app.py").write_text("try:\n    x = 1\nexcept:\n    pass\n")
        result = analyze_project(tmp_path)
        pattern_ids = [p["id"] for p in result["rules"]["anti_patterns"]]
        assert "detected-empty-catch" in pattern_ids

    def test_ignores_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("eval('x')")
        result = analyze_project(tmp_path)
        # Empty project returns error dict
        assert "error" in result or result.get("files_analyzed", 0) == 0


class TestFormatAnalysis:
    """Test analysis output formatting."""

    def test_error_result(self):
        output = format_analysis({"error": "No files"})
        assert "Error" in output

    def test_text_format(self, tmp_path):
        (tmp_path / "a.py").write_text("eval(x)")
        result = analyze_project(tmp_path)
        output = format_analysis(result, format="text")
        assert "Language" in output
        assert "python" in output

    def test_json_format(self, tmp_path):
        (tmp_path / "a.py").write_text("eval(x)")
        result = analyze_project(tmp_path)
        output = format_analysis(result, format="json")
        data = json.loads(output)
        assert data["language"] == "python"


class TestPatternDetectors:
    """Test that all pattern detectors have required fields."""

    def test_all_detectors_have_fields(self):
        for detector in PATTERN_DETECTORS:
            assert "id" in detector
            assert "pattern" in detector
            assert "name" in detector
            assert "severity" in detector
            assert "category" in detector
            assert "message" in detector
            assert "fix_hint" in detector

    def test_patterns_are_valid_regex(self):
        import re

        for detector in PATTERN_DETECTORS:
            try:
                re.compile(detector["pattern"])
            except re.error:
                pytest.fail(f"Invalid regex in detector {detector['id']}: {detector['pattern']}")
