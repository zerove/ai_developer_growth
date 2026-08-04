"""Tests for rule_editor.py (0% → target 85%)."""

from __future__ import annotations

from unittest.mock import patch

from tools.scripts.rule_editor import HTML, EditorHandler, main


class TestEditorHandler:
    """Tests for EditorHandler."""

    def test_get_html_content(self) -> None:
        handler = EditorHandler.__new__(EditorHandler)
        html = handler.get_html_content()
        assert "<!DOCTYPE html>" in html
        assert "Rule Editor" in html

    def test_page_title(self) -> None:
        assert "Rule Editor" in EditorHandler.page_title


class TestHTML:
    """Tests for HTML template."""

    def test_is_valid_html(self) -> None:
        assert "<html" in HTML
        assert "</html>" in HTML

    def test_has_editor(self) -> None:
        assert "yaml-editor" in HTML

    def test_has_validate_button(self) -> None:
        assert "validate" in HTML.lower()


class TestMain:
    """Tests for main() function."""

    def test_default_port(self) -> None:
        with patch("sys.argv", ["prog"]):
            with patch("tools.scripts.rule_editor.run_server") as mock_run:
                ret = main()
                assert ret == 0
                _, kwargs = mock_run.call_args
                assert kwargs["port"] == 8081

    def test_custom_port(self) -> None:
        with patch("sys.argv", ["prog", "--port", "9090"]):
            with patch("tools.scripts.rule_editor.run_server") as mock_run:
                ret = main()
                assert ret == 0
                _, kwargs = mock_run.call_args
                assert kwargs["port"] == 9090
