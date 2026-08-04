"""Tests for rule_visualize.py (54% → target 85%)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.scripts.rule_visualize import (
    HTML_TEMPLATE,
    VisualizeHandler,
    get_all_rules,
    main,
)


class TestGetAllRules:
    """Tests for get_all_rules()."""

    def test_no_langs_dir(self, tmp_path: Path) -> None:
        with patch("tools.scripts.rule_visualize._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path / "nonexistent"
            result = get_all_rules()
            assert result == {}

    def test_with_languages(self, tmp_path: Path) -> None:
        langs_dir = tmp_path / "languages"
        py_dir = langs_dir / "python"
        py_dir.mkdir(parents=True)
        rules_dir = py_dir / "rules.d"
        rules_dir.mkdir()
        (rules_dir / "anti.yml").write_text(
            "anti_patterns:\n  - id: py-test\n    pattern: 'bad'\n    message: 'test rule'\n    severity: error\n"
        )
        with (
            patch("tools.scripts.rule_visualize._rules_dir") as mock_dir,
            patch("tools.scripts.rule_visualize.load_rules") as mock_load,
        ):
            mock_dir.return_value = tmp_path
            mock_load.return_value = {
                "anti_patterns": [{"id": "py-test"}],
                "naming_conventions": [],
                "complexity": [],
            }
            result = get_all_rules()
            assert "python" in result
            assert result["python"]["total"] == 1
            assert len(result["python"]["anti_patterns"]) == 1

    def test_skip_non_dirs(self, tmp_path: Path) -> None:
        langs_dir = tmp_path / "languages"
        langs_dir.mkdir()
        (langs_dir / "file.txt").write_text("not a dir")
        with patch("tools.scripts.rule_visualize._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = get_all_rules()
            assert result == {}

    def test_empty_lang_dir(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "python"
        lang_dir.mkdir(parents=True)
        with (
            patch("tools.scripts.rule_visualize._rules_dir") as mock_dir,
            patch("tools.scripts.rule_visualize.load_rules") as mock_load,
        ):
            mock_dir.return_value = tmp_path
            mock_load.return_value = {"anti_patterns": [], "naming_conventions": [], "complexity": []}
            result = get_all_rules()
            assert "python" in result
            assert result["python"]["total"] == 0


class TestVisualizeHandler:
    """Tests for VisualizeHandler."""

    def test_api_rules(self) -> None:
        handler = VisualizeHandler.__new__(VisualizeHandler)
        with patch("tools.scripts.rule_visualize.get_all_rules") as mock_rules:
            mock_rules.return_value = {
                "python": {"anti_patterns": [], "naming_conventions": [], "complexity": [], "total": 0}
            }
            result = handler.handle_api("/api/rules", {})
            assert "python" in result

    def test_api_languages(self) -> None:
        handler = VisualizeHandler.__new__(VisualizeHandler)
        with patch("tools.scripts.rule_visualize.get_all_rules") as mock_rules:
            mock_rules.return_value = {"python": {"total": 5}, "rust": {"total": 3}}
            result = handler.handle_api("/api/languages", {})
            assert result["python"] == 5
            assert result["rust"] == 3

    def test_api_stats(self) -> None:
        handler = VisualizeHandler.__new__(VisualizeHandler)
        with patch("tools.scripts.rule_visualize.get_all_rules") as mock_rules:
            mock_rules.return_value = {"python": {"total": 10}, "rust": {"total": 5}}
            result = handler.handle_api("/api/stats", {})
            assert result["languages"] == 2
            assert result["total_rules"] == 15
            assert result["by_lang"]["python"] == 10

    def test_api_unknown_endpoint(self) -> None:
        handler = VisualizeHandler.__new__(VisualizeHandler)
        result = handler.handle_api("/api/unknown", {})
        assert "error" in result

    def test_get_html_content(self) -> None:
        handler = VisualizeHandler.__new__(VisualizeHandler)
        html = handler.get_html_content()
        assert "<!DOCTYPE html>" in html
        assert "AI Language Rules" in html

    def test_page_title(self) -> None:
        assert VisualizeHandler.page_title == "AI Language Rules - Visual Browser"


class TestHTMLTemplate:
    """Tests for HTML_TEMPLATE."""

    def test_is_valid_html(self) -> None:
        assert "<html" in HTML_TEMPLATE
        assert "</html>" in HTML_TEMPLATE
        assert "<script>" in HTML_TEMPLATE

    def test_has_api_endpoints(self) -> None:
        assert "/api/rules" in HTML_TEMPLATE

    def test_has_search(self) -> None:
        assert "search" in HTML_TEMPLATE.lower()


class TestMain:
    """Tests for main() function."""

    def test_default_port(self) -> None:
        with patch("sys.argv", ["prog"]):
            with patch("tools.scripts.rule_visualize.run_server") as mock_run:
                ret = main()
                assert ret == 0
                mock_run.assert_called_once()
                _, kwargs = mock_run.call_args
                assert kwargs["port"] == 8080

    def test_custom_port(self) -> None:
        with patch("sys.argv", ["prog", "--port", "9090"]):
            with patch("tools.scripts.rule_visualize.run_server") as mock_run:
                ret = main()
                assert ret == 0
                _, kwargs = mock_run.call_args
                assert kwargs["port"] == 9090

    def test_lang_arg(self) -> None:
        with patch("sys.argv", ["prog", "--lang", "python"]):
            with patch("tools.scripts.rule_visualize.run_server"):
                ret = main()
                assert ret == 0
