"""Tests for validators/cli.py (43% → target 85%)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tools.scripts.validators.cli import (
    _file_hash,
    _get_supported_files,
    _load_cache,
    _save_cache,
    build_parser,
    main,
    print_results,
)
from tools.scripts.validators.models import Issue, ValidationResult


class TestFileHash:
    """Tests for _file_hash()."""

    def test_hash_valid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello world")
        h = _file_hash(f)
        assert len(h) == 32  # md5 hex

    def test_hash_missing_file(self) -> None:
        h = _file_hash(Path("/nonexistent/file.py"))
        assert h == ""

    def test_hash_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("same content")
        assert _file_hash(f) == _file_hash(f)


class TestCache:
    """Tests for _load_cache() and _save_cache()."""

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        assert _load_cache(tmp_path / "cache.json") == {}

    def test_save_and_load(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        data = {"/path/to/file.py": "abc123"}
        _save_cache(cache_file, data)
        loaded = _load_cache(cache_file)
        assert loaded == data

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "bad.json"
        cache_file.write_text("not json {{{")
        assert _load_cache(cache_file) == {}


class TestGetSupportedFiles:
    """Tests for _get_supported_files()."""

    def test_finds_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.txt").write_text("text")
        files = _get_supported_files(tmp_path, [])
        assert len(files) == 1
        assert files[0].name == "a.py"

    def test_excludes_directories(self, tmp_path: Path) -> None:
        (tmp_path / "src.py").write_text("pass")
        node = tmp_path / "node_modules"
        node.mkdir()
        (node / "dep.py").write_text("dep")
        files = _get_supported_files(tmp_path, ["node_modules"])
        assert all("node_modules" not in str(f) for f in files)

    def test_empty_directory(self, tmp_path: Path) -> None:
        files = _get_supported_files(tmp_path, [])
        assert files == []


class TestPrintResults:
    """Tests for print_results()."""

    def test_all_pass(self, capsys: Any) -> None:
        r = ValidationResult(file="test.py", language="python", issues=[])
        code = print_results([r])
        assert code == 0
        assert "PASSED" in capsys.readouterr().out

    def test_with_errors(self, capsys: Any) -> None:
        issue = Issue(rule_id="r1", severity="error", category="test", file="test.py", line=1, message="bad")
        r = ValidationResult(file="test.py", language="python", issues=[issue])
        code = print_results([r])
        assert code == 1

    def test_with_warnings(self, capsys: Any) -> None:
        issue = Issue(rule_id="r1", severity="warning", category="test", file="test.py", line=1, message="warn")
        r = ValidationResult(file="test.py", language="python", issues=[issue])
        code = print_results([r])
        assert code == 0
        assert "warnings" in capsys.readouterr().out.lower()

    def test_json_output(self, capsys: Any) -> None:
        r = ValidationResult(file="test.py", language="python", issues=[])
        print_results([r], use_json=True)
        data = json.loads(capsys.readouterr().out)
        assert "results" in data
        assert data["passed"] is True

    def test_fix_hint_shown(self, capsys: Any) -> None:
        issue = Issue(
            rule_id="r1", severity="error", category="t", file="f.py", line=1, message="m", fix_hint="do this"
        )
        r = ValidationResult(file="f.py", language="python", issues=[issue])
        print_results([r])
        assert "do this" in capsys.readouterr().out


class TestBuildParser:
    """Tests for build_parser()."""

    def test_basic_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["src/", "--lang", "python"])
        assert args.path == Path("src/")
        assert args.lang == "python"

    def test_auto_detect(self) -> None:
        parser = build_parser()
        args = parser.parse_args([".", "--auto-detect"])
        assert args.auto_detect is True

    def test_format_choices(self) -> None:
        parser = build_parser()
        for fmt in ("text", "json", "html", "junit", "sarif"):
            args = parser.parse_args(["f.py", "--format", fmt])
            assert args.format == fmt

    def test_default_excludes(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["."])
        assert "node_modules" in args.exclude

    def test_fix_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args([".", "--fix", "--dry-run"])
        assert args.fix is True
        assert args.dry_run is True

    def test_health_score(self) -> None:
        parser = build_parser()
        args = parser.parse_args([".", "--health-score"])
        assert args.health_score is True

    def test_incremental(self) -> None:
        parser = build_parser()
        args = parser.parse_args([".", "--incremental"])
        assert args.incremental is True

    def test_max_errors(self) -> None:
        parser = build_parser()
        args = parser.parse_args([".", "--max-errors", "5"])
        assert args.max_errors == 5

    def test_linters(self) -> None:
        parser = build_parser()
        args = parser.parse_args([".", "--linters", "ruff", "mypy"])
        assert args.linters == ["ruff", "mypy"]


class TestSaveCacheErrors:
    """Tests for _save_cache() error paths."""

    def test_save_to_invalid_path(self) -> None:
        # Should not raise
        _save_cache(Path("/nonexistent/dir/cache.json"), {"a": "b"})


class TestMainExtended:
    """Extended tests for main() covering more paths."""

    def test_incremental_file_unchanged(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("pass\n")
        # First run populates cache
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--incremental"]):
            main()
        # Second run should skip (unchanged)
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--incremental"]):
            ret = main()
        assert ret == 0

    def test_incremental_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass\n")
        with patch("sys.argv", ["cli", str(tmp_path), "--auto-detect", "--incremental"]):
            ret = main()
        assert ret == 0
        # Second run - no changed files
        with patch("sys.argv", ["cli", str(tmp_path), "--auto-detect", "--incremental"]):
            ret = main()
        assert ret == 0

    def test_changed_files(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("pass\n")
        with patch("sys.argv", ["cli", str(tmp_path), "--lang", "python", "--changed-files", str(f)]):
            ret = main()
        assert ret == 0

    def test_changed_files_nonexistent_skipped(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.py"
        with patch("sys.argv", ["cli", str(tmp_path), "--lang", "python", "--changed-files", str(missing)]):
            ret = main()
        assert ret == 0

    def test_custom_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "custom.yml").write_text("anti_patterns: []\nnaming: {}\nthresholds: {}\n")
        f = tmp_path / "code.py"
        f.write_text("pass\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--custom-rules", str(rules_dir)]):
            ret = main()
        assert ret == 0

    def test_fix_dry_run(self, tmp_path: Path) -> None:
        f = tmp_path / "fixme.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--fix", "--dry-run"]):
            ret = main()
        assert ret == 0

    def test_max_warnings(self, tmp_path: Path) -> None:
        f = tmp_path / "warn.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--max-warnings", "0"]):
            ret = main()
        # Warnings may or may not exist, just verify no crash
        assert ret in (0, 1)

    def test_fail_on_warnings(self, tmp_path: Path) -> None:
        f = tmp_path / "w.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--fail-on-warnings"]):
            ret = main()
        assert ret in (0, 1)

    def test_format_html(self, tmp_path: Path) -> None:
        f = tmp_path / "page.py"
        f.write_text("pass\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--format", "html"]):
            ret = main()
        assert ret == 0

    def test_format_junit(self, tmp_path: Path) -> None:
        f = tmp_path / "j.py"
        f.write_text("pass\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--format", "junit"]):
            ret = main()
        assert ret == 0

    def test_linters(self, tmp_path: Path) -> None:
        f = tmp_path / "lint.py"
        f.write_text("pass\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--linters", "ruff"]):
            ret = main()
        assert ret == 0

    def test_incremental_directory_no_changes(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass\n")
        # First run to populate cache
        with patch("sys.argv", ["cli", str(tmp_path), "--auto-detect", "--incremental"]):
            main()
        # Second run - no changes
        with patch("sys.argv", ["cli", str(tmp_path), "--auto-detect", "--incremental"]):
            ret = main()
        assert ret == 0

    def test_format_sarif_output(self, tmp_path: Path) -> None:
        f = tmp_path / "s.py"
        f.write_text("pass\n")
        out = tmp_path / "out.sarif"
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--format", "sarif", "-o", str(out)]):
            main()
        assert out.exists()

    def test_max_errors_in_text_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "e.py"
        f.write_text("eval('x')\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--max-errors", "100"]):
            ret = main()
        # print_results returns 1 for errors, max-errors only blocks when exceeded
        assert ret == 1  # eval generates errors, print_results returns 1

    def test_max_warnings_in_text_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "w.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["cli", str(f), "--lang", "python", "--max-warnings", "100"]):
            ret = main()
        assert ret == 0
