"""Tests for validators/pipeline.py (83% → target 90%)."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.scripts.rules_engine.validators.models import ValidationResult
from tools.scripts.rules_engine.validators.pipeline import (
    EXTENSION_MAP,
    _get_embedded_rules,
    _merge_rules,
    _rules_hash,
    check_anti_patterns,
    detect_language_from_file,
    load_custom_rules,
    validate_directory,
    validate_file,
)


class TestDetectLanguage:
    """Tests for detect_language_from_file()."""

    def test_python(self, tmp_path: Path) -> None:
        assert detect_language_from_file(tmp_path / "test.py") == "python"

    def test_typescript(self, tmp_path: Path) -> None:
        assert detect_language_from_file(tmp_path / "app.ts") == "typescript"

    def test_rust(self, tmp_path: Path) -> None:
        assert detect_language_from_file(tmp_path / "main.rs") == "rust"

    def test_unknown_extension(self, tmp_path: Path) -> None:
        assert detect_language_from_file(tmp_path / "file.xyz") is None

    def test_case_insensitive(self, tmp_path: Path) -> None:
        assert detect_language_from_file(tmp_path / "test.PY") == "python"

    def test_all_extensions_mapped(self) -> None:
        for ext, lang in EXTENSION_MAP.items():
            f = Path(f"test{ext}")
            assert detect_language_from_file(f) == lang


class TestCheckAntiPatterns:
    """Tests for check_anti_patterns()."""

    def test_no_patterns(self) -> None:
        result = check_anti_patterns(["x = 1"], {}, "test.py")
        assert result == []

    def test_match_found(self) -> None:
        rules = {
            "anti_patterns": [
                {
                    "id": "a1",
                    "pattern": r"eval\(",
                    "severity": "error",
                    "message": "no eval",
                }
            ]
        }
        result = check_anti_patterns(["eval('x')"], rules, "f.py")
        assert len(result) == 1
        assert result[0].rule_id == "a1"

    def test_comment_lines_skipped(self) -> None:
        rules = {"anti_patterns": [{"id": "a1", "pattern": r"eval\(", "severity": "error", "message": "m"}]}
        result = check_anti_patterns(["# eval('x')"], rules, "f.py")
        assert result == []

    def test_no_match(self) -> None:
        rules = {"anti_patterns": [{"id": "a1", "pattern": r"eval\(", "severity": "error", "message": "m"}]}
        result = check_anti_patterns(["pass"], rules, "f.py")
        assert result == []

    def test_multiple_patterns(self) -> None:
        rules = {
            "anti_patterns": [
                {
                    "id": "a1",
                    "pattern": r"eval\(",
                    "severity": "error",
                    "message": "m1",
                },
                {
                    "id": "a2",
                    "pattern": r"exec\(",
                    "severity": "error",
                    "message": "m2",
                },
            ]
        }
        result = check_anti_patterns(["eval('x'); exec('y')"], rules, "f.py")
        assert len(result) == 2


class TestMergeRules:
    """Tests for _merge_rules()."""

    def test_merge_new_patterns(self) -> None:
        base = {"anti_patterns": [{"id": "a"}]}
        custom = {"anti_patterns": [{"id": "b"}]}
        result = _merge_rules(base, custom)
        ids = {p["id"] for p in result["anti_patterns"]}
        assert ids == {"a", "b"}

    def test_merge_override_by_id(self) -> None:
        base = {"anti_patterns": [{"id": "a", "severity": "low"}]}
        custom = {"anti_patterns": [{"id": "a", "severity": "high"}]}
        result = _merge_rules(base, custom)
        assert result["anti_patterns"][0]["severity"] == "high"

    def test_severity_override(self) -> None:
        base = {"anti_patterns": [{"id": "a", "severity": "low"}]}
        custom = {"anti_patterns": [{"id": "a", "severity_override": "critical"}]}
        result = _merge_rules(base, custom)
        assert result["anti_patterns"][0]["severity"] == "critical"

    def test_merge_naming(self) -> None:
        base = {"naming": {"func": "snake"}}
        custom = {"naming": {"cls": "Pascal"}}
        result = _merge_rules(base, custom)
        assert result["naming"]["func"] == "snake"
        assert result["naming"]["cls"] == "Pascal"

    def test_merge_thresholds(self) -> None:
        base = {"thresholds": {"max_lines": 100}}
        custom = {"thresholds": {"max_complexity": 10}}
        result = _merge_rules(base, custom)
        assert result["thresholds"]["max_lines"] == 100
        assert result["thresholds"]["max_complexity"] == 10


class TestLoadCustomRules:
    """Tests for load_custom_rules()."""

    def test_no_ai_rules_dir(self, tmp_path: Path) -> None:
        result = load_custom_rules(tmp_path)
        assert result["anti_patterns"] == []

    def test_load_yml_files(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "custom.yml").write_text(
            yaml.dump(
                {
                    "anti_patterns": [
                        {
                            "id": "c1",
                            "pattern": r"FIXME",
                            "severity": "warning",
                            "message": "fixme found",
                        }
                    ],
                    "naming": {
                        "func": {
                            "pattern": r"[a-z]",
                            "severity": "info",
                            "message": "msg",
                        }
                    },
                    "thresholds": {"max_lines": 50},
                }
            )
        )
        result = load_custom_rules(tmp_path)
        assert len(result["anti_patterns"]) == 1
        assert result["naming"]["func"]["pattern"] == r"[a-z]"
        assert result["thresholds"]["max_lines"] == 50


class TestGetEmbeddedRules:
    """Tests for _get_embedded_rules()."""

    def test_returns_rules(self) -> None:
        result = _get_embedded_rules("python")
        assert "anti_patterns" in result
        assert len(result["anti_patterns"]) == 2

    def test_rust_prefix(self) -> None:
        result = _get_embedded_rules("rust")
        ids = {r["id"] for r in result["anti_patterns"]}
        assert ids == {"rs-eval-exec", "rs-hardcoded-secret"}


class TestValidateFile:
    """Tests for validate_file()."""

    def test_valid_python_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        result = validate_file(f, "python")
        assert isinstance(result, ValidationResult)
        assert result.lines_checked == 1

    def test_file_with_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("eval('x')\n")
        result = validate_file(f, "python")
        assert len(result.issues) > 0

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.py"
        result = validate_file(f, "python")
        assert len(result.issues) > 0


class TestValidateDirectory:
    """Tests for validate_directory()."""

    def test_validates_all_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass\n")
        (tmp_path / "b.py").write_text("eval('x')\n")
        results = validate_directory(tmp_path, "python")
        assert len(results) == 2

    def test_excludes_directories(self, tmp_path: Path) -> None:
        (tmp_path / "good.py").write_text("pass\n")
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "bad.py").write_text("eval('x')\n")
        results = validate_directory(tmp_path, "python", exclude=["vendor"])
        assert len(results) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        results = validate_directory(tmp_path, "python")
        assert results == []


class TestRulesHash:
    """Tests for _rules_hash()."""

    def test_nonexistent(self) -> None:
        h = _rules_hash("nonexistent_lang_xyz")
        assert h == ""
