"""Phase 28+29: Tests for validators/pipeline.py, rules_engine/checker.py, rules_engine/rule_loader.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.rules_engine.validators.pipeline import (
    _get_embedded_rules,
    _load_common_rules,
    _merge_common_rules,
    _merge_rules,
    _rules_hash,
    check_anti_patterns,
    detect_language_from_file,
    load_custom_rules,
    load_rules,
    validate_directory,
    validate_file,
)


class TestDetectLanguageFromFile:
    def test_python(self) -> None:
        assert detect_language_from_file(Path("main.py")) == "python"

    def test_typescript(self) -> None:
        assert detect_language_from_file(Path("app.tsx")) == "typescript"

    def test_unknown(self) -> None:
        assert detect_language_from_file(Path("file.xyz")) is None


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

    def test_common_change_invalidates_hash(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "testlang" / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text("anti_patterns: []\n")
        common = tmp_path / "common" / "security.yml"
        common.parent.mkdir()
        common.write_text("anti_patterns: []\n")
        before = _rules_hash("testlang", tmp_path)
        common.write_text("anti_patterns:\n- id: x\n  pattern: y\n")
        assert _rules_hash("testlang", tmp_path) != before

    def test_missing_common_still_hashes_language(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "testlang" / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text("anti_patterns: []\n")
        assert len(_rules_hash("testlang", tmp_path)) == 64


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


class TestMergeRules:
    def test_new_patterns_added(self) -> None:
        base = {"anti_patterns": [{"id": "r1", "severity": "error"}]}
        custom = {"anti_patterns": [{"id": "r2", "severity": "warning"}]}
        result = _merge_rules(base, custom)
        ids = {p["id"] for p in result["anti_patterns"]}
        assert ids == {"r1", "r2"}

    def test_existing_pattern_overridden(self) -> None:
        base = {"anti_patterns": [{"id": "r1", "severity": "error", "pattern": "old"}]}
        custom = {"anti_patterns": [{"id": "r1", "severity": "warning", "pattern": "new"}]}
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

    def test_common_rule_superseded_by_language_rule(self) -> None:
        """语言规则声明 supersedes 时，common 中的同 ID 规则被跳过。"""
        base = {"anti_patterns": [{"id": "lang-eval", "supersedes": ["common-eval"]}]}
        common = {"anti_patterns": [{"id": "common-eval"}, {"id": "common-other"}]}
        result = _merge_common_rules(base, common)
        assert [p["id"] for p in result["anti_patterns"]] == ["lang-eval", "common-other"]

    def test_supersedes_does_not_drop_custom_rule(self) -> None:
        """supersedes 只作用于 common 合并，用户自定义规则仍可覆盖。"""
        base = {"anti_patterns": [{"id": "lang-eval", "supersedes": ["common-eval"]}]}
        custom = {"anti_patterns": [{"id": "common-eval", "severity": "warning"}]}
        result = _merge_rules(base, custom)
        assert [p["id"] for p in result["anti_patterns"]] == ["lang-eval", "common-eval"]


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


class TestLoadCustomRulesExtended:
    def test_no_ai_rules_dir(self, tmp_path: Path) -> None:
        result = load_custom_rules(tmp_path)
        assert result == {"anti_patterns": [], "naming": {}, "thresholds": {}}

    def test_valid_custom_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "custom.yml").write_text("anti_patterns:\n- id: my-rule\n  severity: warning\n  pattern: test\n")
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
        (rules_dir / "c.yml").write_text("naming:\n  func: snake_case\nthresholds:\n  max_lines: 200\n")
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


class TestCheckAntiPatterns:
    def test_match_found(self) -> None:
        lines = ["x = eval('bad')"]
        rules = {"anti_patterns": [{"id": "r1", "severity": "error", "pattern": r"eval\("}]}
        issues = check_anti_patterns(lines, rules, "test.py")
        assert len(issues) >= 1

    def test_no_match(self) -> None:
        lines = ["x = 1"]
        rules = {"anti_patterns": [{"id": "r1", "severity": "error", "pattern": r"eval\("}]}
        issues = check_anti_patterns(lines, rules, "test.py")
        assert issues == []

    def test_no_patterns_key(self) -> None:
        issues = check_anti_patterns(["x = 1"], {}, "test.py")
        assert issues == []

    def test_exclude_patterns_skip_line(self) -> None:
        rules = {
            "anti_patterns": [
                {
                    "id": "r1",
                    "severity": "error",
                    "pattern": r"password\s*=",
                    "exclude_patterns": [r"https?://"],
                }
            ]
        }
        lines = ['password = "secret"', 'password = "https://example.com"']
        issues = check_anti_patterns(lines, rules, "test.py")
        assert [issue.line for issue in issues] == [1]


class TestValidateFileExtended:
    def test_validate_with_custom_rules(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = eval('bad')\n")
        custom = {"anti_patterns": [{"id": "custom-r", "severity": "error", "pattern": r"eval\("}]}
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
        result = validate_file(f, "python", custom_rules={"anti_patterns": [], "thresholds": {}})
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


class TestDiskCache:
    # ADR-075: 本类原先直写**真实的** ``tools/.cache/rules_engine/
    # rules_cache.json`` (模块级硬编码路径), 而 ``test_rule_loader_disk_cache``
    # 已正确 monkeypatch 到 tmp_path。两者在 ``-n 8`` 下并发时互相覆盖,
    # 实测导致 ``test_save_and_load`` 偶发失败:
    #   AssertionError: assert 'python:abc' in {}
    # 即缓存被别的 worker 写成了不含本用例 key 的内容 —— 与被测代码无关的
    # 纯粹交叉污染。故此处也重定向到 tmp_path, 不碰工作区。
    @pytest.fixture(autouse=True)
    def _redirect_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.rules_engine import rule_loader as rl

        cache_file = tmp_path / "rules_cache.json"
        monkeypatch.setattr(rl, "_DISK_CACHE_DIR", tmp_path)
        monkeypatch.setattr(rl, "_DISK_CACHE_FILE", cache_file)

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
