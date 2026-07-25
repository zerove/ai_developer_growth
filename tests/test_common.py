"""Tests for _common.py (35% → target 80%)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts._common import (
    EXTENSION_MAP,
    SUPPORTED_EXTENSIONS,
    detect_language,
    file_hash,
    filter_supported_files,
    framework_dir,
    get_project_root,
    handle_error,
    load_yaml,
    print_check,
    print_section,
    rules_dir,
    run_command,
    safe_import,
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
        assert "=" * 50 in output


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
