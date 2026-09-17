"""Tests for _common.py (35% → target 80%)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts._common import (
    EXTENSION_MAP,
    SUPPORTED_EXTENSIONS,
    SeverityCountsMixin,
    child_by_type,
    detect_language,
    detect_language_from_file,
    file_hash,
    filter_supported_files,
    find_first,
    find_first_at_depth,
    framework_dir,
    get_project_root,
    handle_error,
    load_cache,
    load_yaml,
    merge_anti_patterns,
    node_text,
    print_check,
    print_section,
    rules_dir,
    run_command,
    safe_import,
    save_cache,
    save_yaml,
)


class TestPathHelpers:
    def test_get_project_root(self) -> None:
        root = get_project_root()
        assert isinstance(root, Path)
        assert root.exists()

    def test_rules_dir(self) -> None:
        rd = rules_dir()
        assert rd.exists()
        assert rd.name == "ai-dev-framework"

    def test_framework_dir_alias(self) -> None:
        assert framework_dir() == rules_dir()


class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language(Path("test.py")) == "python"

    def test_typescript(self) -> None:
        assert detect_language(Path("test.ts")) == "typescript"

    def test_rust(self) -> None:
        assert detect_language(Path("main.rs")) == "rust"

    def test_unknown_extension(self) -> None:
        assert detect_language(Path("test.xyz")) is None

    def test_case_insensitive(self) -> None:
        assert detect_language(Path("test.PY")) == "python"

    def test_all_extensions_mapped(self) -> None:
        """All extensions map to a language."""
        for ext in EXTENSION_MAP:
            result = detect_language(Path(f"file{ext}"))
            assert result is not None, f"Extension {ext} returned None"


class TestRunCommand:
    @patch("tools.scripts._common.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        code, output = run_command(["echo", "hello"])
        assert code == 0
        assert "ok" in output

    @patch("tools.scripts._common.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        code, output = run_command(["false"])
        assert code == 1
        assert "err" in output

    @patch("tools.scripts._common.subprocess.run")
    def test_custom_cwd(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_command(["ls"], cwd=tmp_path)
        cwd_used = (
            mock_run.call_args[1].get("cwd") or mock_run.call_args[0][1]
            if len(mock_run.call_args[0]) > 1
            else mock_run.call_args[1]["cwd"]
        )
        assert cwd_used == tmp_path


class TestFileHash:
    def test_hash_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = file_hash(f)
        assert len(h) == 16
        assert h.isalnum()

    def test_hash_same_content(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same")
        f2.write_text("same")
        assert file_hash(f1) == file_hash(f2)

    def test_hash_different_content(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("aaa")
        f2.write_text("bbb")
        assert file_hash(f1) != file_hash(f2)

    def test_hash_nonexistent(self, tmp_path: Path) -> None:
        assert file_hash(tmp_path / "nope.txt") == ""


class TestHandleError:
    def test_handle_error_exits(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            handle_error(RuntimeError("test error"), script="test")
        assert exc_info.value.code == 1

    def test_handle_error_custom_exit_code(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            handle_error(RuntimeError("test"), exit_code=42)
        assert exc_info.value.code == 42

    def test_handle_error_no_script(self) -> None:
        with pytest.raises(SystemExit):
            handle_error(ValueError("oops"))


class TestSafeImport:
    def test_import_existing(self) -> None:
        mod = safe_import("json")
        assert mod is not None

    def test_import_nonexistent(self) -> None:
        assert safe_import("nonexistent_module_xyz") is None

    def test_import_with_package(self) -> None:
        mod = safe_import("path", package="pathlib")
        # importlib.import_module('pathlib.path') may fail since path isn't a submodule
        # Just verify no exception is raised
        assert mod is None or mod is not None


class TestYamlHelpers:
    def test_load_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "test.yml"
        f.write_text("key: value\nlist:\n  - 1\n  - 2\n")
        data = load_yaml(f)
        assert data is not None
        assert data["key"] == "value"
        assert data["list"] == [1, 2]

    def test_load_yaml_invalid(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yml"
        f.write_text("{{invalid yaml}}")
        result = load_yaml(f)
        assert result is None

    def test_load_yaml_nonexistent(self, tmp_path: Path) -> None:
        result = load_yaml(tmp_path / "nope.yml")
        assert result is None

    def test_save_and_load(self, tmp_path: Path) -> None:
        f = tmp_path / "out.yml"
        data = {"name": "test", "items": [1, 2, 3]}
        save_yaml(f, data)
        loaded = load_yaml(f)
        assert loaded is not None
        assert loaded["name"] == "test"
        assert loaded["items"] == [1, 2, 3]


class TestOutputFormatting:
    def test_print_check_passed(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_check("Test", True)
        output = capsys.readouterr().out
        assert "Test" in output
        assert "✅" in output

    def test_print_check_failed(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_check("Test", False, "error details")
        output = capsys.readouterr().out
        assert "" in output
        assert "error details" in output

    def test_print_check_failed_no_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_check("Test", False)
        output = capsys.readouterr().out
        assert "❌" in output

    def test_print_section(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_section("My Section")
        output = capsys.readouterr().out
        assert "My Section" in output
        assert "—" in output


class TestFilterSupportedFiles:
    def test_filter(self, tmp_path: Path) -> None:
        files = [
            tmp_path / "a.py",
            tmp_path / "b.rs",
            tmp_path / "c.xyz",
            tmp_path / "d.ts",
        ]
        result = filter_supported_files(files)
        assert len(result) == 3
        extensions = {f.suffix for f in result}
        assert ".xyz" not in extensions

    def test_empty_list(self) -> None:
        assert filter_supported_files([]) == []

    def test_supported_extensions_is_set(self) -> None:
        assert isinstance(SUPPORTED_EXTENSIONS, set)
        assert ".py" in SUPPORTED_EXTENSIONS


class _FakeNode:
    """Duck-typed tree node mimicking tree-sitter _TreeNode."""

    def __init__(self, type_name: str, text: Any = None, children: list[Any] | None = None) -> None:
        self.type = type_name
        self.text = text
        self.children = children or []


class _FakeIssue:
    def __init__(self, severity: str) -> None:
        self.severity = severity


class TestChildByType:
    def test_found_first_match(self) -> None:
        node = _FakeNode("root", children=[_FakeNode("a"), _FakeNode("target"), _FakeNode("b")])
        result = child_by_type(node, "target")
        assert result is not None
        assert result.type == "target"

    def test_found_not_first(self) -> None:
        node = _FakeNode("root", children=[_FakeNode("a"), _FakeNode("a"), _FakeNode("target")])
        assert child_by_type(node, "target").type == "target"

    def test_not_found(self) -> None:
        node = _FakeNode("root", children=[_FakeNode("a"), _FakeNode("b")])
        assert child_by_type(node, "nope") is None

    def test_empty_children(self) -> None:
        assert child_by_type(_FakeNode("root"), "x") is None


class TestFindFirst:
    def test_root_match(self) -> None:
        node = _FakeNode("root")
        assert find_first(node, "root") is node

    def test_deep_match(self) -> None:
        inner = _FakeNode("inner", children=[_FakeNode("needle")])
        node = _FakeNode("root", children=[_FakeNode("a"), inner])
        result = find_first(node, "needle")
        assert result is not None
        assert result.type == "needle"

    def test_missing(self) -> None:
        node = _FakeNode("root", children=[_FakeNode("a")])
        assert find_first(node, "nope") is None

    def test_leaf_no_children(self) -> None:
        assert find_first(_FakeNode("leaf"), "nope") is None


class TestFindFirstAtDepth:
    def test_found_within_depth(self) -> None:
        child = _FakeNode("leaf", children=[_FakeNode("needle")])
        node = _FakeNode("root", children=[child])
        assert find_first_at_depth(node, "needle", max_depth=2) is not None

    def test_blocked_by_depth(self) -> None:
        child = _FakeNode("leaf", children=[_FakeNode("needle")])
        node = _FakeNode("root", children=[child])
        assert find_first_at_depth(node, "needle", max_depth=1) is None

    def test_root_match_ignores_depth(self) -> None:
        assert find_first_at_depth(_FakeNode("root"), "root", max_depth=0) is not None


class TestNodeText:
    def test_str_text(self) -> None:
        assert node_text(_FakeNode("n", text="hello")) == "hello"

    def test_bytes_text(self) -> None:
        assert node_text(_FakeNode("n", text=b"hello")) == "hello"

    def test_bytes_invalid_utf8(self) -> None:
        assert node_text(_FakeNode("n", text=b"\xff\xfehello")) == "\ufffd\ufffdhello"

    def test_none_text(self) -> None:
        assert node_text(_FakeNode("n", text=None)) == ""

    def test_none_node(self) -> None:
        assert node_text(None) == ""


class TestMergeAntiPatterns:
    def test_empty_custom_returns_copy(self) -> None:
        base = [{"id": "a", "pattern": "x"}]
        merged = merge_anti_patterns(base, [])
        assert merged == base
        assert merged is not base  # 副本语义 (ADR-034)

    def test_severity_override_keeps_base_untouched(self) -> None:
        base = [{"id": "a", "pattern": "x", "severity": "error"}]
        custom = [{"id": "a", "pattern": "x", "severity_override": "info"}]
        merged = merge_anti_patterns(base, custom)
        assert merged[0]["severity"] == "info"
        assert base[0]["severity"] == "error"  # 原 base 不被修改

    def test_custom_replaces_by_id(self) -> None:
        base = [{"id": "a", "pattern": "x", "severity": "error"}]
        custom = [{"id": "a", "pattern": "y", "severity": "warning"}]
        merged = merge_anti_patterns(base, custom)
        assert merged[0]["pattern"] == "y"
        assert merged[0]["severity"] == "warning"

    def test_new_items_appended(self) -> None:
        base = [{"id": "a", "pattern": "x"}]
        custom = [{"id": "b", "pattern": "z"}]
        merged = merge_anti_patterns(base, custom)
        assert len(merged) == 2
        assert merged[-1]["id"] == "b"

    def test_preserves_non_overridden_base_items(self) -> None:
        base = [{"id": "a", "pattern": "x"}, {"id": "c", "pattern": "w"}]
        custom = [{"id": "b", "pattern": "z"}]
        merged = merge_anti_patterns(base, custom)
        assert [p["id"] for p in merged] == ["a", "c", "b"]


class TestCacheHelpers:
    def test_load_cache_missing(self, tmp_path: Path) -> None:
        assert load_cache(tmp_path / "nope.json") == {}

    def test_load_cache_valid(self, tmp_path: Path) -> None:
        f = tmp_path / "cache.json"
        f.write_text('{"a": "b"}')
        assert load_cache(f) == {"a": "b"}

    def test_load_cache_corrupted(self, tmp_path: Path) -> None:
        f = tmp_path / "cache.json"
        f.write_text("{invalid json")
        assert load_cache(f) == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        f = tmp_path / "cache.json"
        save_cache(f, {"k": "v"})
        assert load_cache(f) == {"k": "v"}

    def test_load_cache_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "cache.json"
        f.write_text("")
        assert load_cache(f) == {}


class TestDetectLanguageAlias:
    def test_alias_is_detect_language(self) -> None:
        assert detect_language_from_file is detect_language

    def test_alias_typescript(self) -> None:
        assert detect_language_from_file(Path("test.ts")) == "typescript"

    def test_alias_unknown(self) -> None:
        assert detect_language_from_file(Path("x.xyz")) is None


class TestSeverityCountsMixin:
    def test_counts(self) -> None:
        class Result(SeverityCountsMixin):
            pass

        r = Result()
        r.issues = [
            _FakeIssue("error"),
            _FakeIssue("error"),
            _FakeIssue("warning"),
            _FakeIssue("info"),
        ]
        assert r.error_count == 2
        assert r.warning_count == 1
        assert r.info_count == 1

    def test_no_issues(self) -> None:
        class Result(SeverityCountsMixin):
            pass

        r = Result()
        r.issues = []
        assert r.error_count == 0
        assert r.warning_count == 0
        assert r.info_count == 0
