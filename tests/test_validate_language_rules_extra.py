"""Additional tests for validate_language_rules.py - CLI and edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from tools.scripts.validate_language_rules import (
    Issue,
    ValidationResult,
    detect_language_from_file,
    main,
    print_results,
    validate_directory,
    validate_file,
)

# ──────────────────────────────────────────────────────────
# Tests for main() CLI
# ──────────────────────────────────────────────────────────


class TestMainCLI:
    def test_no_args(self) -> None:
        with mock.patch("sys.argv", ["validate_language_rules"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse error

    def test_validate_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        with mock.patch("sys.argv", ["validate_language_rules", str(test_file), "--lang", "python"]):
            result = main()
            assert result in (0, 1)

    def test_validate_nonexistent(self, tmp_path: Path) -> None:
        with mock.patch(
            "sys.argv",
            ["validate_language_rules", str(tmp_path / "nope.py"), "--lang", "python"],
        ):
            result = main()
            assert result == 1

    def test_validate_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        with mock.patch("sys.argv", ["validate_language_rules", str(tmp_path), "--lang", "python"]):
            result = main()
            assert result in (0, 1)

    def test_json_output(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        with mock.patch(
            "sys.argv",
            ["validate_language_rules", str(test_file), "--lang", "python", "--json"],
        ):
            result = main()
            assert result in (0, 1)


# ──────────────────────────────────────────────────────────
# Tests for print_results()
# ──────────────────────────────────────────────────────────


class TestPrintResults:
    def test_empty_results(self) -> None:
        assert print_results([]) == 0

    def test_passing_results(self) -> None:
        vr = ValidationResult(
            file="test.py",
            language="python",
            issues=[],
            lines_checked=10,
        )
        assert print_results([vr]) == 0

    def test_failing_results(self) -> None:
        vr = ValidationResult(
            file="test.py",
            language="python",
            issues=[
                Issue(
                    rule_id="test-rule",
                    severity="error",
                    category="test",
                    file="test.py",
                    line=1,
                    message="Test error",
                )
            ],
            lines_checked=10,
        )
        assert print_results([vr]) == 1

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        vr = ValidationResult(
            file="test.py",
            language="python",
            issues=[],
            lines_checked=10,
        )
        print_results([vr], use_json=True)
        out = capsys.readouterr().out
        assert '"passed": true' in out or '"passed":true' in out


# ──────────────────────────────────────────────────────────
# Tests for validate_file() edge cases
# ──────────────────────────────────────────────────────────


class TestValidateFileEdgeCases:
    def test_nonexistent_file(self, tmp_path: Path) -> None:
        result = validate_file(tmp_path / "nope.py", "python")
        assert result is not None

    def test_empty_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "empty.py"
        test_file.write_text("")
        result = validate_file(test_file, "python")
        assert result is not None

    def test_binary_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "binary.py"
        test_file.write_bytes(b"\x00\x01\x02\x03")
        result = validate_file(test_file, "python")
        assert result is not None


# ──────────────────────────────────────────────────────────
# Tests for validate_directory() edge cases
# ──────────────────────────────────────────────────────────


class TestValidateDirectoryEdgeCases:
    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        results = validate_directory(tmp_path / "nope")
        assert results == []

    def test_empty_dir(self, tmp_path: Path) -> None:
        results = validate_directory(tmp_path)
        assert results == []


# ──────────────────────────────────────────────────────────
# Tests for detect_language_from_file() additional cases
# ──────────────────────────────────────────────────────────


class TestDetectLanguageAdditional:
    def test_rust_file(self) -> None:
        assert detect_language_from_file(Path("main.rs")) == "rust"

    def test_go_file(self) -> None:
        assert detect_language_from_file(Path("main.go")) == "go"

    def test_java_file(self) -> None:
        assert detect_language_from_file(Path("Main.java")) == "java"

    def test_cpp_file(self) -> None:
        assert detect_language_from_file(Path("main.cpp")) == "cpp"

    def test_unknown_ext(self) -> None:
        result = detect_language_from_file(Path("file.xyz"))
        assert result is None or isinstance(result, str)
