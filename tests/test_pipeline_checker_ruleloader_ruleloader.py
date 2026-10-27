# 拆分自 tests/test_pipeline_checker_ruleloader.py

"""Phase 28+29: Tests for validators/pipeline.py, rules_engine/checker.py, rules_engine/rule_loader.py."""

from __future__ import annotations

import json
from pathlib import Path

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


class TestSaveCache:
    def test_save_cache(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.rule_loader import _save_cache

        cache_file = tmp_path / "cache.json"
        _save_cache(cache_file, {"key1": "value1"})
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["key1"] == "value1"


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


class TestRuleLoaderGetEmbedded:
    def test_python(self) -> None:
        rules = rl_get_embedded("python")
        assert "anti_patterns" in rules

    def test_unknown_lang(self) -> None:
        rules = rl_get_embedded("xyz")
        assert "anti_patterns" in rules


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


class TestRuleLoaderLoadCustomRules:
    def test_no_dir(self, tmp_path: Path) -> None:
        result = rl_load_custom(tmp_path)
        assert result["anti_patterns"] == []

    def test_with_valid_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "c.yml").write_text("anti_patterns:\n- id: my-rule\n  severity: error\n")
        result = rl_load_custom(tmp_path)
        assert len(result["anti_patterns"]) == 1

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "bad.yml").write_text("{{bad")
        result = rl_load_custom(tmp_path)
        assert result["anti_patterns"] == []
