# 拆分自 tests/test_pipeline_checker_ruleloader.py

"""Phase 28+29: Tests for validators/pipeline.py, rules_engine/checker.py, rules_engine/rule_loader.py."""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts.rules_engine.checker import (
    _detect_language as checker_detect_language,
)
from tools.scripts.rules_engine.checker import (
    _file_not_found_result,
    _map_severity,
    _parse_linter_output,
    _run_all_checkers,
)
from tools.scripts.rules_engine.checker import (
    check_directory as engine_check_directory,
)
from tools.scripts.rules_engine.checker import (
    check_file as engine_check_file,
)


class TestCheckerDetectLanguage:
    def test_python(self) -> None:
        assert checker_detect_language(Path("main.py")) == "python"

    def test_rust(self) -> None:
        assert checker_detect_language(Path("lib.rs")) == "rust"

    def test_unknown(self) -> None:
        assert checker_detect_language(Path("file.xyz")) == "unknown"

    def test_cpp_variants(self) -> None:
        assert checker_detect_language(Path("a.cpp")) == "cpp"
        assert checker_detect_language(Path("b.cc")) == "cpp"
        assert checker_detect_language(Path("c.cxx")) == "cpp"

    def test_c_and_h(self) -> None:
        assert checker_detect_language(Path("a.c")) == "c"
        assert checker_detect_language(Path("b.h")) == "c"


class TestMapSeverity:
    def test_known_severities(self) -> None:
        assert _map_severity("error") == "error"
        assert _map_severity("warning") == "warning"
        assert _map_severity("info") == "warning"  # info maps to warning

    def test_unknown_severity(self) -> None:
        assert _map_severity("critical") == "error"
        assert _map_severity("") == "warning"

    def test_int_severity(self) -> None:
        assert _map_severity(2) == "error"
        assert _map_severity(1) == "warning"


class TestParseLinterOutput:
    def test_ruff_json_output(self) -> None:
        output = json.dumps(
            [
                {
                    "code": "E302",
                    "message": "expected 2 blank lines",
                    "location": {"row": 5, "column": 1},
                    "fix": None,
                }
            ]
        )
        issues = _parse_linter_output(output, "python", "test.py")
        assert len(issues) >= 1

    def test_empty_output(self) -> None:
        issues = _parse_linter_output("[]", "python", "test.py")
        assert issues == []

    def test_invalid_json(self) -> None:
        issues = _parse_linter_output("not json", "python", "test.py")
        assert issues == []

    def test_eslint_output(self) -> None:
        output = json.dumps(
            [
                {
                    "filePath": "test.js",
                    "messages": [
                        {
                            "ruleId": "no-eval",
                            "message": "eval is dangerous",
                            "line": 10,
                            "column": 5,
                            "severity": 2,
                        }
                    ],
                }
            ]
        )
        issues = _parse_linter_output(output, "javascript", "test.js")
        assert len(issues) >= 1


class TestFileNotFoundResult:
    def test_returns_error(self) -> None:
        result = _file_not_found_result(Path("missing.py"))
        assert result.skipped is True
        assert any(i.rule_id == "file-not-found" for i in result.issues)


class TestCheckerCheckFileExtended:
    def test_nonexistent_file(self) -> None:
        result = engine_check_file(Path("nonexistent.py"))
        assert result.skipped is True
        assert any(i.rule_id == "file-not-found" for i in result.issues)

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        result = engine_check_file(f)
        assert result.skipped is True

    def test_unknown_language(self, tmp_path: Path) -> None:
        f = tmp_path / "file.xyz"
        f.write_text("hello")
        result = engine_check_file(f)
        assert result.skipped is True

    def test_binary_file(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\xff")
        result = engine_check_file(f)
        assert result.skipped is True

    def test_python_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        result = engine_check_file(f, language="python")
        assert result.language == "python"
        assert isinstance(result.issues, list)

    def test_with_custom_rules(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = eval('bad')\n")
        rules = {"anti_patterns": [{"id": "r1", "severity": "error", "pattern": r"eval\("}]}
        result = engine_check_file(f, rules=rules, language="python")
        assert any(i.rule_id == "r1" for i in result.issues)


class TestRunAllCheckers:
    def test_with_python(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        rules = {"anti_patterns": [], "naming": {}, "thresholds": {}}
        issues = _run_all_checkers(f, "x = 1\n", ["x = 1"], "python", rules)
        assert isinstance(issues, list)

    def test_with_javascript(self, tmp_path: Path) -> None:
        f = tmp_path / "test.js"
        f.write_text("var x = 1;\n")
        rules = {"anti_patterns": [], "naming": {}, "thresholds": {}}
        issues = _run_all_checkers(f, "var x = 1;\n", ["var x = 1;"], "javascript", rules)
        assert isinstance(issues, list)

    def test_with_unknown_lang(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("hello")
        rules = {"anti_patterns": []}
        issues = _run_all_checkers(f, "hello\n", ["hello"], "unknown", rules)
        assert isinstance(issues, list)


class TestCheckerCheckDirectory:
    def test_with_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        results = engine_check_directory(tmp_path)
        assert len(results) >= 1

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        results = engine_check_directory(tmp_path / "nope")
        assert results == []

    def test_with_language_filter(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.rs").write_text("fn main() {}")
        results = engine_check_directory(tmp_path, languages=["python"])
        assert len(results) == 1

    def test_skip_git_dirs(self, tmp_path: Path) -> None:
        git = tmp_path / ".git"
        git.mkdir()
        (git / "config").write_text("hello")
        results = engine_check_directory(tmp_path)
        assert results == []

    def test_skip_pycache(self, tmp_path: Path) -> None:
        pyc = tmp_path / "__pycache__"
        pyc.mkdir()
        (pyc / "mod.py").write_text("x = 1\n")
        results = engine_check_directory(tmp_path)
        assert results == []

    def test_not_a_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "file.py"
        f.write_text("x = 1\n")
        results = engine_check_directory(f)
        assert results == []
