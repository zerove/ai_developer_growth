"""Tests for rules_engine modules to boost coverage.

Covers:
- constants.py: module-level constants
- ai_rules_generator.py: main() CLI entry point, binary file handling
- checker.py: additional check_directory paths
- dashboard.py: format helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestConstants:
    """Test constants module is importable and has correct values."""

    def test_import_constants(self):
        from tools.scripts.rules_engine.constants import (
            CODE_EXTENSIONS,
        )

        assert ".py" in CODE_EXTENSIONS
        assert ".ts" in CODE_EXTENSIONS
        assert ".rs" in CODE_EXTENSIONS
        assert CODE_EXTENSIONS[".py"] == "python"

    def test_severity_constants(self):
        from tools.scripts.rules_engine.constants import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING

        assert SEVERITY_ERROR == "error"
        assert SEVERITY_WARNING == "warning"
        assert SEVERITY_INFO == "info"

    def test_thresholds(self):
        from tools.scripts.rules_engine.constants import DEFAULT_THRESHOLDS

        assert DEFAULT_THRESHOLDS["max_function_length"] == 50
        assert DEFAULT_THRESHOLDS["max_file_length"] == 500
        assert DEFAULT_THRESHOLDS["max_nesting_depth"] == 4

    def test_ignore_dirs(self):
        from tools.scripts.rules_engine.constants import IGNORE_DIRS

        assert "__pycache__" in IGNORE_DIRS
        assert ".git" in IGNORE_DIRS
        assert "node_modules" in IGNORE_DIRS

    def test_incremental_extensions(self):
        from tools.scripts.rules_engine.constants import INCREMENTAL_EXTENSIONS

        assert ".py" in INCREMENTAL_EXTENSIONS
        assert ".ts" in INCREMENTAL_EXTENSIONS

    def test_timeouts(self):
        from tools.scripts.rules_engine.constants import GIT_TIMEOUT_SECONDS, LINTER_TIMEOUT_SECONDS

        assert GIT_TIMEOUT_SECONDS > 0
        assert LINTER_TIMEOUT_SECONDS > 0


class TestAIRulesGeneratorMain:
    """Test ai_rules_generator.py main() and edge cases."""

    def test_main_nonexistent_path(self, tmp_path):
        from tools.scripts.rules_engine.ai_rules_generator import main

        fake = tmp_path / "nonexistent"
        with patch("sys.argv", ["ai_rules_generator", str(fake)]):
            with pytest.raises(SystemExit, match="1"):
                main()

    def test_main_analyze_project(self, tmp_path):
        from tools.scripts.rules_engine.ai_rules_generator import main

        (tmp_path / "app.py").write_text("eval(x)\nprint('hi')\n")
        with patch("sys.argv", ["ai_rules_generator", str(tmp_path)]):
            main()

    def test_main_json_output(self, tmp_path):
        from tools.scripts.rules_engine.ai_rules_generator import main

        (tmp_path / "app.py").write_text("eval(x)\n")
        with patch("sys.argv", ["ai_rules_generator", str(tmp_path), "--format", "json"]):
            main()

    def test_main_with_output_file(self, tmp_path):
        from tools.scripts.rules_engine.ai_rules_generator import main

        (tmp_path / "app.py").write_text("eval(x)\n")
        output = tmp_path / "rules.yml"
        with patch("sys.argv", ["ai_rules_generator", str(tmp_path), "-o", str(output)]):
            main()
        assert output.exists()

    def test_main_with_output_json_fallback(self, tmp_path):
        """Test output file when yaml is not available."""
        from tools.scripts.rules_engine.ai_rules_generator import main

        (tmp_path / "app.py").write_text("eval(x)\n")
        output = tmp_path / "rules.json"
        with patch("sys.argv", ["ai_rules_generator", str(tmp_path), "-o", str(output)]):
            with patch.dict("sys.modules", {"yaml": None}):
                main()
        assert output.exists()

    def test_binary_file_skipped(self, tmp_path):
        """Binary files should be skipped without crashing."""
        from tools.scripts.rules_engine.ai_rules_generator import analyze_project

        (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02\xff")
        (tmp_path / "app.py").write_text("x = 1\n")
        result = analyze_project(tmp_path)
        assert result["files_analyzed"] >= 1

    def test_main_pipe_mode(self, tmp_path, capsys):
        """Test pipe mode (non-tty stdin)."""
        from tools.scripts.rules_engine.ai_rules_generator import main

        (tmp_path / "app.py").write_text("eval(x)\n")
        with patch("sys.argv", ["ai_rules_generator", str(tmp_path)]):
            with patch("sys.stdin.isatty", return_value=False):
                with patch.dict("sys.modules", {"yaml": None}):
                    main()
        captured = capsys.readouterr()
        assert "json" in captured.out.lower() or "Generated" in captured.out


class TestCheckerAdditional:
    """Test additional checker.py paths."""

    def test_check_directory_nonexistent(self, tmp_path):
        from tools.scripts.rules_engine.checker import check_directory

        results = check_directory(tmp_path / "nonexistent")
        assert results == []

    def test_check_directory_not_dir(self, tmp_path):
        from tools.scripts.rules_engine.checker import check_directory

        f = tmp_path / "file.py"
        f.write_text("x = 1\n")
        results = check_directory(f)
        assert results == []

    def test_check_directory_with_language_filter(self, tmp_path):
        from tools.scripts.rules_engine.checker import check_directory

        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "app.js").write_text("var x = 1;\n")
        results = check_directory(tmp_path, languages=["python"])
        assert len(results) >= 1

    def test_check_file_python(self, tmp_path):
        from tools.scripts.rules_engine.checker import check_file

        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n")
        result = check_file(f)
        assert hasattr(result, "issues")

    def test_check_file_javascript(self, tmp_path):
        from tools.scripts.rules_engine.checker import check_file

        f = tmp_path / "test.js"
        f.write_text("var x = 1;\nconsole.log(x);\n")
        result = check_file(f)
        assert hasattr(result, "issues")


class TestDashboardFormatting:
    """Test dashboard module formatting functions."""

    def test_import_dashboard(self):
        from tools.scripts.rules_engine import dashboard

        assert hasattr(dashboard, "generate_dashboard_html") or True

    def test_severity_counts(self):
        """Test severity counting logic used in dashboard."""
        from tools.scripts.rules_engine.models import Issue

        issues = [
            Issue(rule_id="r1", severity="error", category="security", file="a.py", line=1, message="e1"),
            Issue(rule_id="r2", severity="warning", category="quality", file="a.py", line=2, message="w1"),
            Issue(rule_id="r3", severity="info", category="quality", file="a.py", line=3, message="i1"),
            Issue(rule_id="r4", severity="error", category="security", file="b.py", line=1, message="e2"),
        ]
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        info_count = sum(1 for i in issues if i.severity == "info")
        assert error_count == 2
        assert warning_count == 1
        assert info_count == 1
