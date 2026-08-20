"""Tests for report.py - HTML audit report generation."""

import os
import tempfile

from src.report import generate_html_report, save_report


class TestGenerateHTMLReport:
    def test_empty_violations(self):
        html_content = generate_html_report([])
        assert "No violations found" in html_content
        assert "<!DOCTYPE html>" in html_content

    def test_with_violations(self):
        violations = [
            {
                "severity": "Critical",
                "rule_id": "R1",
                "message": "Type error",
                "file": "src/main.py",
                "line": 10,
            },
            {
                "severity": "Warning",
                "rule_id": "R2",
                "message": "Long function",
                "file": "src/utils.py",
                "line": 25,
            },
        ]
        html_content = generate_html_report(violations)
        assert "Critical" in html_content
        assert "Warning" in html_content
        assert "Type error" in html_content
        assert "src/main.py:10" in html_content

    def test_custom_title(self):
        html_content = generate_html_report([], project_name="My Project")
        assert "My Project" in html_content


class TestSaveReport:
    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "docs", "report.html")
            result = save_report("<html>test</html>", output_path)
            assert os.path.exists(result)
            with open(result, "r") as f:
                assert f.read() == "<html>test</html>"

    def test_save_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "a", "b", "c", "report.html")
            save_report("<html>test</html>", output_path)
            assert os.path.exists(output_path)
