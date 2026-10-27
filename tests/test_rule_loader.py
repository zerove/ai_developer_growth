"""Tests for rules_engine/rule_loader.py - rule loading, caching, merging."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from rules_engine.rule_loader import (
    _file_hash,
    _get_embedded_rules,
    _load_common_rules,
    _load_disk_cache,
    _merge_anti_patterns,
    _merge_rules,
    _save_disk_cache,
    get_language_rules,
    load_custom_rules,
    load_rules,
    load_rules_for_language,
)

# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────


@pytest.fixture
def fw_dir(tmp_path: Path) -> Path:
    """Create a mock framework directory with rules."""
    d = tmp_path / "framework"
    rules_dir = d / "languages" / "python" / "rules.d"
    rules_dir.mkdir(parents=True)
    anti = rules_dir / "anti_patterns.yml"
    anti.write_text(
        yaml.dump(
            {
                "anti_patterns": [
                    {
                        "id": "py-eval",
                        "name": "eval usage",
                        "severity": "error",
                        "category": "security",
                        "pattern": r"\beval\s*\(",
                        "message": "eval is dangerous",
                        "fix_hint": "Use ast.literal_eval",
                    },
                    {
                        "id": "py-print",
                        "name": "print usage",
                        "severity": "warning",
                        "category": "style",
                        "pattern": r"\bprint\s*\(",
                        "message": "Use logging",
                    },
                ],
                "thresholds": {"max_complexity": 10},
                "naming": {"function": "snake_case"},
            }
        )
    )
    # Common security rules
    common_dir = d / "common"
    common_dir.mkdir()
    (common_dir / "security.yml").write_text(
        yaml.dump(
            {
                "anti_patterns": [
                    {
                        "id": "cs-eval",
                        "name": "eval exec",
                        "severity": "error",
                        "category": "security",
                        "pattern": r"\beval\s*\(",
                        "message": "eval is a security risk",
                    }
                ]
            }
        )
    )
    return d


# ──────────────────────────────────────────────────────────
# Tests for _file_hash
# ──────────────────────────────────────────────────────────


class TestFileHash:
    def test_hash_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = _file_hash(f)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_nonexistent(self, tmp_path: Path) -> None:
        assert _file_hash(tmp_path / "nope.txt") == ""

    def test_hash_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("content")
        assert _file_hash(f) == _file_hash(f)


# ──────────────────────────────────────────────────────────
# Tests for disk cache
# ──────────────────────────────────────────────────────────


class TestDiskCache:
    def test_load_nonexistent(self, tmp_path: Path) -> None:
        with mock.patch("rules_engine.rule_loader._DISK_CACHE_FILE", tmp_path / "cache.json"):
            assert _load_disk_cache() == {}

    def test_load_valid(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps({"key": {"data": 1}}))
        with mock.patch("rules_engine.rule_loader._DISK_CACHE_FILE", cache_file):
            result = _load_disk_cache()
            assert result == {"key": {"data": 1}}

    def test_load_corrupted(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("not json")
        with mock.patch("rules_engine.rule_loader._DISK_CACHE_FILE", cache_file):
            assert _load_disk_cache() == {}

    def test_save_and_load(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        with mock.patch("rules_engine.rule_loader._DISK_CACHE_FILE", cache_file):
            with mock.patch("rules_engine.rule_loader._DISK_CACHE_DIR", tmp_path):
                _save_disk_cache({"test": "data"})
            result = _load_disk_cache()
            assert result == {"test": "data"}

    def test_save_oserror(self, tmp_path: Path) -> None:
        with mock.patch(
            "rules_engine.rule_loader._DISK_CACHE_DIR",
            tmp_path / "nonexistent" / "deep",
        ):
            # Should not raise
            _save_disk_cache({"test": "data"})


# ──────────────────────────────────────────────────────────
# Tests for _merge_anti_patterns
# ──────────────────────────────────────────────────────────


class TestMergeAntiPatterns:
    def test_empty_custom(self) -> None:
        base = [{"id": "a", "severity": "error"}]
        assert _merge_anti_patterns(base, []) == base

    def test_new_patterns_appended(self) -> None:
        base = [{"id": "a"}]
        custom = [{"id": "b"}]
        result = _merge_anti_patterns(base, custom)
        assert len(result) == 2
        assert result[1]["id"] == "b"

    def test_override_by_id(self) -> None:
        base = [{"id": "a", "severity": "error", "message": "old"}]
        custom = [{"id": "a", "severity": "warning", "message": "new"}]
        result = _merge_anti_patterns(base, custom)
        assert len(result) == 1
        assert result[0]["message"] == "new"

    def test_severity_override(self) -> None:
        base = [{"id": "a", "severity": "error", "message": "keep"}]
        custom = [{"id": "a", "severity_override": "info"}]
        result = _merge_anti_patterns(base, custom)
        assert len(result) == 1
        assert result[0]["severity"] == "info"
        assert result[0]["message"] == "keep"  # base message kept


# ──────────────────────────────────────────────────────────
# Tests for _merge_rules
# ──────────────────────────────────────────────────────────


class TestMergeRules:
    def test_merge_anti_patterns(self) -> None:
        base = {"anti_patterns": [{"id": "a"}], "thresholds": {"max": 10}}
        custom = {"anti_patterns": [{"id": "b"}]}
        result = _merge_rules(base, custom)
        assert len(result["anti_patterns"]) == 2

    def test_merge_naming(self) -> None:
        base = {"naming": {"function": "snake_case"}}
        custom = {"naming": {"class": "PascalCase"}}
        result = _merge_rules(base, custom)
        assert result["naming"]["function"] == "snake_case"
        assert result["naming"]["class"] == "PascalCase"

    def test_merge_thresholds_override(self) -> None:
        base = {"thresholds": {"max": 10}}
        custom = {"thresholds": {"max": 20}}
        result = _merge_rules(base, custom)
        assert result["thresholds"]["max"] == 20

    def test_merge_preserves_base(self) -> None:
        base = {"anti_patterns": [{"id": "a"}], "extra": "keep"}
        result = _merge_rules(base, {})
        assert result["extra"] == "keep"


# ──────────────────────────────────────────────────────────
# Tests for _load_common_rules
# ──────────────────────────────────────────────────────────


class TestLoadCommonRules:
    def test_loads_common(self, fw_dir: Path) -> None:
        result = _load_common_rules(fw_dir)
        assert "anti_patterns" in result
        assert len(result["anti_patterns"]) >= 1

    def test_nonexistent(self, tmp_path: Path) -> None:
        assert _load_common_rules(tmp_path / "nope") == {}


# ──────────────────────────────────────────────────────────
# Tests for _get_embedded_rules
# ──────────────────────────────────────────────────────────


class TestGetEmbeddedRules:
    def test_returns_fallback(self) -> None:
        rules = _get_embedded_rules("python")
        assert "anti_patterns" in rules
        assert len(rules["anti_patterns"]) == 2
        assert rules["anti_patterns"][0]["id"].startswith("py-")

    def test_different_language_prefix(self) -> None:
        rules = _get_embedded_rules("rust")
        assert rules["anti_patterns"][0]["id"].startswith("rs-")


# ──────────────────────────────────────────────────────────
# Tests for load_rules
# ──────────────────────────────────────────────────────────


class TestLoadRules:
    def setup_method(self) -> None:
        from rules_engine.rule_loader import _RULE_CACHE

        _RULE_CACHE.clear()

    def test_loads_from_yaml(self, fw_dir: Path) -> None:
        rules = load_rules("python", fw_dir)
        assert "anti_patterns" in rules
        assert len(rules["anti_patterns"]) >= 2

    def test_returns_embedded_when_missing(self, tmp_path: Path) -> None:
        rules = load_rules("nonexistent", tmp_path)
        assert "anti_patterns" in rules

    def test_caching(self, fw_dir: Path) -> None:
        r1 = load_rules("python", fw_dir)
        r2 = load_rules("python", fw_dir)
        assert r1 is r2  # same object from cache

    def test_merges_common_security(self, fw_dir: Path) -> None:
        rules = load_rules("python", fw_dir)
        rule_ids = {r["id"] for r in rules.get("anti_patterns", [])}
        assert "cs-eval" in rule_ids  # from common/security.yml


# ──────────────────────────────────────────────────────────
# Tests for load_custom_rules
# ──────────────────────────────────────────────────────────


class TestLoadCustomRules:
    def test_no_ai_rules_dir(self, tmp_path: Path) -> None:
        result = load_custom_rules(tmp_path)
        assert result["anti_patterns"] == []

    def test_loads_custom_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "custom.yml").write_text(
            yaml.dump(
                {
                    "anti_patterns": [{"id": "custom-rule", "severity": "error", "pattern": "x"}],
                    "naming": {"function": "camelCase"},
                    "thresholds": {"max_lines": 500},
                }
            )
        )
        result = load_custom_rules(tmp_path)
        assert len(result["anti_patterns"]) == 1
        assert result["naming"]["function"] == "camelCase"
        assert result["thresholds"]["max_lines"] == 500

    def test_skips_invalid_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "bad.yml").write_text("not: valid: yaml: [")
        result = load_custom_rules(tmp_path)
        assert result["anti_patterns"] == []


# ──────────────────────────────────────────────────────────
# Tests for load_rules_for_language
# ──────────────────────────────────────────────────────────


class TestLoadRulesForLanguage:
    def setup_method(self) -> None:
        from rules_engine.rule_loader import _RULE_CACHE

        _RULE_CACHE.clear()

    def test_includes_security(self, fw_dir: Path) -> None:
        rules = load_rules_for_language("python", fw_dir)
        rule_ids = {r["id"] for r in rules.get("anti_patterns", [])}
        # Should have both language rules and security patterns
        assert any("py-" in rid for rid in rule_ids)


# ──────────────────────────────────────────────────────────
# Tests for get_language_rules
# ──────────────────────────────────────────────────────────


class TestGetLanguageRules:
    def setup_method(self) -> None:
        from rules_engine.rule_loader import _RULE_CACHE

        _RULE_CACHE.clear()

    def test_returns_rules(self, fw_dir: Path) -> None:
        rules = get_language_rules("python")
        assert "anti_patterns" in rules
