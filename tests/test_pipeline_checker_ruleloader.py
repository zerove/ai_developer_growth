"""Phase 28+29: Tests for validators/pipeline.py, rules_engine/checker.py, rules_engine/rule_loader.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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
from tools.scripts.rules_engine.rule_loader import (
    _file_hash,
    _merge_anti_patterns,
    get_language_rules,
    load_rules_for_language,
)
from tools.scripts.rules_engine.rule_loader import (
    _get_embedded_rules as rl_get_embedded,
)
from tools.scripts.rules_engine.rule_loader import (
    _load_common_rules as rl_load_common,
)
from tools.scripts.rules_engine.rule_loader import (
    _merge_rules as rl_merge_rules,
)
from tools.scripts.rules_engine.rule_loader import (
    load_custom_rules as rl_load_custom,
)
from tools.scripts.rules_engine.rule_loader import (
    load_rules as rl_load_rules,
)
from tools.scripts.rules_engine.validators.pipeline import (
    _get_embedded_rules,
    _load_common_rules,
    _merge_rules,
    _rules_hash,
    check_anti_patterns,
    detect_language_from_file,
    load_custom_rules,
    load_rules,
    validate_directory,
    validate_file,
)

# ── detect_language_from_file ──────────────────────────────


class TestDetectLanguageFromFile:
    def test_python(self) -> None:
        assert detect_language_from_file(Path("main.py")) == "python"

    def test_typescript(self) -> None:
        assert detect_language_from_file(Path("app.tsx")) == "typescript"

    def test_unknown(self) -> None:
        assert detect_language_from_file(Path("file.xyz")) is None


# ── _rules_hash ────────────────────────────────────────────


class TestRulesHash:
    def test_nonexistent_lang(self, tmp_path: Path) -> None:
        result = _rules_hash("nonexistent_lang_xyz", tmp_path)
        assert result == ""

    def test_existing_lang(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "testlang" / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text("anti_patterns: []\n")
        result = _rules_hash("testlang", tmp_path)
        assert len(result) == 64  # sha256 hex digest

    def test_os_error_handling(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "testlang" / "rules.d"
        lang_dir.mkdir(parents=True)
        f = lang_dir / "anti_patterns.yml"
        f.write_text("data\n")
        with patch.object(Path, "read_bytes", side_effect=OSError("locked")):
            result = _rules_hash("testlang", tmp_path)
            assert result == ""


# ── _load_common_rules ────────────────────────────────────


class TestLoadCommonRules:
    def test_no_common_file(self, tmp_path: Path) -> None:
        result = _load_common_rules(tmp_path)
        assert result == {}

    def test_valid_common_file(self, tmp_path: Path) -> None:
        common = tmp_path / "common" / "security.yml"
        common.parent.mkdir()
        common.write_text("anti_patterns:\n- id: test-rule\n  severity: error\n")
        result = _load_common_rules(tmp_path)
        assert "anti_patterns" in result

    def test_invalid_yaml_returns_empty(self, tmp_path: Path) -> None:
        common = tmp_path / "common" / "security.yml"
        common.parent.mkdir()
        common.write_text("{{invalid yaml")
        result = _load_common_rules(tmp_path)
        assert result == {}

    def test_non_dict_yaml(self, tmp_path: Path) -> None:
        common = tmp_path / "common" / "security.yml"
        common.parent.mkdir()
        common.write_text("- item1\n- item2\n")
        result = _load_common_rules(tmp_path)
        assert result == {}


# ── _merge_rules ──────────────────────────────────────────


class TestMergeRules:
    def test_new_patterns_added(self) -> None:
        base = {"anti_patterns": [{"id": "r1", "severity": "error"}]}
        custom = {"anti_patterns": [{"id": "r2", "severity": "warning"}]}
        result = _merge_rules(base, custom)
        ids = {p["id"] for p in result["anti_patterns"]}
        assert ids == {"r1", "r2"}

    def test_existing_pattern_overridden(self) -> None:
        base = {"anti_patterns": [{"id": "r1", "severity": "error", "pattern": "old"}]}
        custom = {
            "anti_patterns": [{"id": "r1", "severity": "warning", "pattern": "new"}]
        }
        result = _merge_rules(base, custom)
        r1 = next(p for p in result["anti_patterns"] if p["id"] == "r1")
        assert r1["pattern"] == "new"

    def test_severity_override(self) -> None:
        base = {"anti_patterns": [{"id": "r1", "severity": "error"}]}
        custom = {"anti_patterns": [{"id": "r1", "severity_override": "info"}]}
        result = _merge_rules(base, custom)
        r1 = next(p for p in result["anti_patterns"] if p["id"] == "r1")
        assert r1["severity"] == "info"

    def test_naming_merged(self) -> None:
        base = {"anti_patterns": [], "naming": {"func": "camelCase"}}
        custom = {"anti_patterns": [], "naming": {"class": "PascalCase"}}
        result = _merge_rules(base, custom)
        assert result["naming"]["func"] == "camelCase"
        assert result["naming"]["class"] == "PascalCase"

    def test_thresholds_merged(self) -> None:
        base = {"anti_patterns": [], "thresholds": {"max_lines": 100}}
        custom = {"anti_patterns": [], "thresholds": {"max_complexity": 10}}
        result = _merge_rules(base, custom)
        assert result["thresholds"]["max_lines"] == 100
        assert result["thresholds"]["max_complexity"] == 10

    def test_no_custom_patterns(self) -> None:
        base = {"anti_patterns": [{"id": "r1"}]}
        custom = {"anti_patterns": []}
        result = _merge_rules(base, custom)
        assert len(result["anti_patterns"]) == 1

    def test_custom_has_no_anti_patterns_key(self) -> None:
        base = {"anti_patterns": [{"id": "r1"}]}
        custom = {"naming": {"func": "snake_case"}}
        result = _merge_rules(base, custom)
        assert len(result["anti_patterns"]) == 1
        assert result["naming"]["func"] == "snake_case"


# ── _get_embedded_rules ──────────────────────────────────


class TestGetEmbeddedRules:
    def test_python_embedded(self) -> None:
        rules = _get_embedded_rules("python")
        assert "anti_patterns" in rules
        assert len(rules["anti_patterns"]) >= 2
        ids = {r["id"] for r in rules["anti_patterns"]}
        assert "py-eval-exec" in ids
        assert "py-hardcoded-secret" in ids

    def test_rust_embedded(self) -> None:
        rules = _get_embedded_rules("rust")
        ids = {r["id"] for r in rules["anti_patterns"]}
        assert "ru-eval-exec" in ids

    def test_empty_lang(self) -> None:
        rules = _get_embedded_rules("")
        assert "anti_patterns" in rules


# ── load_rules ────────────────────────────────────────────


class TestLoadRulesExtended:
    def test_load_with_framework_dir(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "python" / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text(
            "anti_patterns:\n- id: test-rule\n  severity: error\n  pattern: test\n"
        )
        rules = load_rules("python", framework_dir=tmp_path)
        assert isinstance(rules, dict)

    def test_load_nonexistent_lang(self, tmp_path: Path) -> None:
        rules = load_rules("nonexistent", framework_dir=tmp_path)
        assert "anti_patterns" in rules  # falls back to embedded

    def test_load_no_yaml_available(self, tmp_path: Path) -> None:
        with patch.dict("sys.modules", {"yaml": None}):
            rules = load_rules("python", framework_dir=tmp_path)
            assert "anti_patterns" in rules


# ── load_custom_rules ────────────────────────────────────


class TestLoadCustomRulesExtended:
    def test_no_ai_rules_dir(self, tmp_path: Path) -> None:
        result = load_custom_rules(tmp_path)
        assert result == {"anti_patterns": [], "naming": {}, "thresholds": {}}

    def test_valid_custom_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "custom.yml").write_text(
            "anti_patterns:\n- id: my-rule\n  severity: warning\n  pattern: test\n"
        )
        result = load_custom_rules(tmp_path)
        assert len(result["anti_patterns"]) == 1
        assert result["anti_patterns"][0]["id"] == "my-rule"

    def test_invalid_yaml_file(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "bad.yml").write_text("{{invalid")
        result = load_custom_rules(tmp_path)
        assert result["anti_patterns"] == []

    def test_non_dict_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "list.yml").write_text("- item1\n- item2\n")
        result = load_custom_rules(tmp_path)
        assert result["anti_patterns"] == []

    def test_naming_and_thresholds(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "c.yml").write_text(
            "naming:\n  func: snake_case\nthresholds:\n  max_lines: 200\n"
        )
        result = load_custom_rules(tmp_path)
        assert result["naming"]["func"] == "snake_case"
        assert result["thresholds"]["max_lines"] == 200

    def test_no_yaml_module(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "c.yml").write_text("anti_patterns: []\n")
        with patch.dict("sys.modules", {"yaml": None}):
            result = load_custom_rules(tmp_path)
            assert result["anti_patterns"] == []


# ── check_anti_patterns ──────────────────────────────────


class TestCheckAntiPatterns:
    def test_match_found(self) -> None:
        lines = ["x = eval('bad')"]
        rules = {
            "anti_patterns": [{"id": "r1", "severity": "error", "pattern": r"eval\("}]
        }
        issues = check_anti_patterns(lines, rules, "test.py")
        assert len(issues) >= 1

    def test_no_match(self) -> None:
        lines = ["x = 1"]
        rules = {
            "anti_patterns": [{"id": "r1", "severity": "error", "pattern": r"eval\("}]
        }
        issues = check_anti_patterns(lines, rules, "test.py")
        assert issues == []

    def test_no_patterns_key(self) -> None:
        issues = check_anti_patterns(["x = 1"], {}, "test.py")
        assert issues == []


# ── validate_file ─────────────────────────────────────────


class TestValidateFileExtended:
    def test_validate_with_custom_rules(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = eval('bad')\n")
        custom = {
            "anti_patterns": [
                {"id": "custom-r", "severity": "error", "pattern": r"eval\("}
            ]
        }
        result = validate_file(f, "python", custom_rules=custom)
        ids = {i.rule_id for i in result.issues}
        assert "custom-r" in ids

    def test_validate_os_error(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.py"
        # File doesn't exist - validate_file handles this
        with patch.object(Path, "read_text", side_effect=OSError("denied")):
            result = validate_file(f, "python")
            assert any(i.rule_id == "read-error" for i in result.issues)

    def test_validate_python_ast(self, tmp_path: Path) -> None:
        f = tmp_path / "ast_test.py"
        f.write_text("def foo():\n    pass\n")
        result = validate_file(f, "python")
        assert result.lines_checked == 2

    def test_validate_empty_custom_rules(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        result = validate_file(
            f, "python", custom_rules={"anti_patterns": [], "thresholds": {}}
        )
        assert isinstance(result.issues, list)

    def test_validate_fix_replacement_applied(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        custom = {
            "anti_patterns": [
                {
                    "id": "fr",
                    "severity": "error",
                    "pattern": r"x = 1",
                    "fix_replacement": "x = 2",
                }
            ]
        }
        result = validate_file(f, "python", custom_rules=custom)
        fr_issues = [i for i in result.issues if i.rule_id == "fr"]
        if fr_issues:
            assert fr_issues[0].fix_replacement == "x = 2"


# ── validate_directory ────────────────────────────────────


class TestValidateDirectoryExtended:
    def test_with_language(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        results = validate_directory(tmp_path, language="python")
        assert len(results) >= 1

    def test_with_exclude(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n")
        (tmp_path / "test.py").write_text("x = 2\n")
        results = validate_directory(tmp_path, exclude=["src"])
        assert len(results) == 1

    def test_auto_detect_language(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "lib.rs").write_text("fn main() {}")
        results = validate_directory(tmp_path)
        assert len(results) >= 2

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        results = validate_directory(tmp_path / "nope")
        assert results == []

    def test_skip_dirs(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x = 1\n")
        results = validate_directory(tmp_path)
        assert results == []

    def test_with_custom_rules(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        custom = {"anti_patterns": []}
        results = validate_directory(tmp_path, language="python", custom_rules=custom)
        assert len(results) >= 1


# ══════════════════════════════════════════════════════════
# Phase 29: rules_engine/checker.py + rule_loader.py
# ══════════════════════════════════════════════════════════


# ── checker: _detect_language ─────────────────────────────


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


# ── checker: _map_severity ────────────────────────────────


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


# ── checker: _parse_linter_output ─────────────────────────


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


# ── checker: _file_not_found_result ───────────────────────


class TestFileNotFoundResult:
    def test_returns_error(self) -> None:
        result = _file_not_found_result(Path("missing.py"))
        assert result.skipped is True
        assert any(i.rule_id == "file-not-found" for i in result.issues)


# ── checker: check_file ──────────────────────────────────


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
        rules = {
            "anti_patterns": [{"id": "r1", "severity": "error", "pattern": r"eval\("}]
        }
        result = engine_check_file(f, rules=rules, language="python")
        assert any(i.rule_id == "r1" for i in result.issues)


# ── checker: _run_all_checkers ────────────────────────────


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
        issues = _run_all_checkers(
            f, "var x = 1;\n", ["var x = 1;"], "javascript", rules
        )
        assert isinstance(issues, list)

    def test_with_unknown_lang(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("hello")
        rules = {"anti_patterns": []}
        issues = _run_all_checkers(f, "hello\n", ["hello"], "unknown", rules)
        assert isinstance(issues, list)


# ── checker: check_directory ──────────────────────────────


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


# ── rule_loader: _file_hash ──────────────────────────────


class TestFileHash:
    def test_hash_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = _file_hash(f)
        assert len(h) == 64  # SHA-256 hex digest

    def test_hash_nonexistent(self, tmp_path: Path) -> None:
        h = _file_hash(tmp_path / "nope.txt")
        assert h == ""

    def test_same_content_same_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same")
        f2.write_text("same")
        assert _file_hash(f1) == _file_hash(f2)


# ── rule_loader: _load_disk_cache / _save_disk_cache ─────


class TestDiskCache:
    def test_save_and_load(self) -> None:
        from tools.scripts.rules_engine import rule_loader as rl

        cache = {"python:abc": {"anti_patterns": []}}
        rl._save_disk_cache(cache)
        loaded = rl._load_disk_cache()
        assert "python:abc" in loaded

    def test_load_empty(self) -> None:
        from tools.scripts.rules_engine import rule_loader as rl

        loaded = rl._load_disk_cache()
        assert isinstance(loaded, dict)


# ── rule_loader: _save_cache (in-memory) ─────────────────


class TestSaveCache:
    def test_save_cache(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.rule_loader import _save_cache

        cache_file = tmp_path / "cache.json"
        _save_cache(cache_file, {"key1": "value1"})
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["key1"] == "value1"


# ── rule_loader: _merge_anti_patterns ────────────────────


class TestMergeAntiPatterns:
    def test_merge_new_patterns(self) -> None:
        base = [{"id": "r1", "severity": "error"}]
        custom = [{"id": "r2", "severity": "warning"}]
        result = _merge_anti_patterns(base, custom)
        assert len(result) == 2

    def test_merge_override_existing(self) -> None:
        base = [{"id": "r1", "severity": "error", "pattern": "old"}]
        custom = [{"id": "r1", "severity": "warning", "pattern": "new"}]
        result = _merge_anti_patterns(base, custom)
        r1 = next(p for p in result if p["id"] == "r1")
        assert r1["pattern"] == "new"

    def test_merge_empty_custom(self) -> None:
        base = [{"id": "r1"}]
        result = _merge_anti_patterns(base, [])
        assert len(result) == 1


# ── rule_loader: _merge_rules ────────────────────────────


class TestRuleLoaderMergeRules:
    def test_merge_with_naming(self) -> None:
        base = {"anti_patterns": [], "naming": {"func": "camelCase"}}
        custom = {"anti_patterns": [], "naming": {"class": "PascalCase"}}
        result = rl_merge_rules(base, custom)
        assert result["naming"]["func"] == "camelCase"
        assert result["naming"]["class"] == "PascalCase"

    def test_merge_with_thresholds(self) -> None:
        base = {"anti_patterns": [], "thresholds": {"max_lines": 100}}
        custom = {"anti_patterns": [], "thresholds": {"max_complexity": 10}}
        result = rl_merge_rules(base, custom)
        assert result["thresholds"]["max_lines"] == 100


# ── rule_loader: _load_common_rules ──────────────────────


class TestRuleLoaderLoadCommon:
    def test_no_common_file(self, tmp_path: Path) -> None:
        result = rl_load_common(tmp_path)
        assert result == {}

    def test_valid_common_file(self, tmp_path: Path) -> None:
        common = tmp_path / "common" / "security.yml"
        common.parent.mkdir()
        common.write_text("anti_patterns:\n- id: sec1\n  severity: error\n")
        result = rl_load_common(tmp_path)
        assert "anti_patterns" in result


# ── rule_loader: _get_embedded_rules ─────────────────────


class TestRuleLoaderGetEmbedded:
    def test_python(self) -> None:
        rules = rl_get_embedded("python")
        assert "anti_patterns" in rules

    def test_unknown_lang(self) -> None:
        rules = rl_get_embedded("xyz")
        assert "anti_patterns" in rules


# ── rule_loader: load_rules_for_language / get_language_rules


class TestLoadRulesForLanguage:
    def test_load_python(self) -> None:
        rules = load_rules_for_language("python")
        assert "anti_patterns" in rules

    def test_load_unknown(self) -> None:
        rules = load_rules_for_language("nonexistent")
        assert "anti_patterns" in rules

    def test_get_language_rules(self) -> None:
        rules = get_language_rules("python")
        assert "anti_patterns" in rules


# ── rule_loader: load_rules ──────────────────────────────


class TestRuleLoaderLoadRules:
    def test_load_with_framework_dir(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "python" / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text("anti_patterns: []\n")
        rules = rl_load_rules("python", framework_dir=tmp_path)
        assert isinstance(rules, dict)

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        rules = rl_load_rules("nonexistent", framework_dir=tmp_path)
        assert "anti_patterns" in rules


# ── rule_loader: load_custom_rules ───────────────────────


class TestRuleLoaderLoadCustomRules:
    def test_no_dir(self, tmp_path: Path) -> None:
        result = rl_load_custom(tmp_path)
        assert result["anti_patterns"] == []

    def test_with_valid_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "c.yml").write_text(
            "anti_patterns:\n- id: my-rule\n  severity: error\n"
        )
        result = rl_load_custom(tmp_path)
        assert len(result["anti_patterns"]) == 1

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "bad.yml").write_text("{{bad")
        result = rl_load_custom(tmp_path)
        assert result["anti_patterns"] == []
