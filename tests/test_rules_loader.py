"""Tests for rules/loader.py (61% → target 90%)."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.scripts.rules_loader.loader import (
    _get_embedded_rules,
    _load_common_rules,
    _load_raw_rules,
    _merge_rules,
    load_custom_rules,
    load_rules,
)


class TestLoadRawRules:
    """Tests for _load_raw_rules()."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.yml"
        f.write_text("anti_patterns:\n  - id: test\n")
        result = _load_raw_rules(str(f))
        assert "anti_patterns" in result

    def test_missing_file_returns_empty(self) -> None:
        result = _load_raw_rules("/nonexistent/path.yml")
        assert result == {}

    def test_non_dict_yaml_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "list.yml"
        f.write_text("- item1\n- item2\n")
        result = _load_raw_rules(str(f))
        assert result == {}

    def test_empty_yaml_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yml"
        f.write_text("")
        result = _load_raw_rules(str(f))
        assert result == {}


class TestMergeRules:
    """Tests for _merge_rules()."""

    def test_merge_new_rules(self) -> None:
        base = {"anti_patterns": [{"id": "a"}]}
        custom = {"anti_patterns": [{"id": "b"}]}
        result = _merge_rules(base, custom)
        ids = {r["id"] for r in result["anti_patterns"]}
        assert ids == {"a", "b"}

    def test_merge_override_by_id(self) -> None:
        base = {"anti_patterns": [{"id": "a", "severity": "low"}]}
        custom = {"anti_patterns": [{"id": "a", "severity": "high"}]}
        result = _merge_rules(base, custom)
        assert result["anti_patterns"][0]["severity"] == "high"

    def test_severity_override_field(self) -> None:
        base = {"anti_patterns": [{"id": "a", "severity": "low"}]}
        custom = {"anti_patterns": [{"id": "a", "severity_override": "critical"}]}
        result = _merge_rules(base, custom)
        assert result["anti_patterns"][0]["severity"] == "critical"

    def test_merge_dict_based(self) -> None:
        base = {"naming_conventions": {"func": "snake"}}
        custom = {"naming_conventions": {"cls": "Pascal"}}
        result = _merge_rules(base, custom)
        assert result["naming_conventions"]["func"] == "snake"
        assert result["naming_conventions"]["cls"] == "Pascal"

    def test_custom_non_dict_item_skipped(self) -> None:
        base = {"anti_patterns": [{"id": "a"}]}
        custom = {"anti_patterns": ["not-a-dict"]}
        result = _merge_rules(base, custom)
        assert len(result["anti_patterns"]) == 1

    def test_empty_custom_items(self) -> None:
        base = {"anti_patterns": [{"id": "a"}]}
        result = _merge_rules(base, {})
        assert result["anti_patterns"] == [{"id": "a"}]

    def test_complexity_category(self) -> None:
        base = {"complexity": [{"id": "c1", "max": 10}]}
        custom = {"complexity": [{"id": "c1", "max": 20}]}
        result = _merge_rules(base, custom)
        assert result["complexity"][0]["max"] == 20

    def test_thresholds_dict_merge(self) -> None:
        base = {"thresholds": {"max_lines": 100}}
        custom = {"thresholds": {"max_complexity": 10}}
        result = _merge_rules(base, custom)
        assert result["thresholds"]["max_lines"] == 100
        assert result["thresholds"]["max_complexity"] == 10

    def test_naming_category_merge(self) -> None:
        base = {"naming": [{"id": "n1"}]}
        custom = {"naming": [{"id": "n2"}]}
        result = _merge_rules(base, custom)
        assert len(result["naming"]) == 2


class TestLoadRules:
    """Tests for load_rules()."""

    def test_load_with_framework_dir(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "python" / "rules.d"
        lang_dir.mkdir(parents=True)
        rules_file = lang_dir / "anti_patterns.yml"
        rules_file.write_text(yaml.dump({"anti_patterns": [{"id": "p1"}]}))
        result = load_rules("python", framework_dir=tmp_path)
        assert "anti_patterns" in result

    def test_load_missing_lang_returns_embedded(self, tmp_path: Path) -> None:
        result = load_rules("nonexistent", framework_dir=tmp_path)
        assert result["language"] == "nonexistent"
        assert "anti_patterns" in result

    def test_load_with_common_rules(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "python" / "rules.d"
        lang_dir.mkdir(parents=True)
        rules_file = lang_dir / "anti_patterns.yml"
        rules_file.write_text(yaml.dump({"anti_patterns": [{"id": "p1"}]}))
        common_dir = tmp_path / "common"
        common_dir.mkdir()
        common_file = common_dir / "security.yml"
        common_file.write_text(yaml.dump({"anti_patterns": [{"id": "sec1"}]}))
        result = load_rules("python", framework_dir=tmp_path)
        ids = {r["id"] for r in result.get("anti_patterns", [])}
        assert "p1" in ids
        assert "sec1" in ids


class TestLoadCustomRules:
    """Tests for load_custom_rules()."""

    def test_no_ai_rules_dir(self, tmp_path: Path) -> None:
        result = load_custom_rules(tmp_path)
        assert result == {}

    def test_load_custom_yml(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / ".ai-rules"
        custom_dir.mkdir()
        f = custom_dir / "my_rules.yml"
        f.write_text(yaml.dump({"anti_patterns": [{"id": "custom1"}]}))
        result = load_custom_rules(tmp_path)
        assert len(result.get("anti_patterns", [])) == 1

    def test_multiple_files_merged(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / ".ai-rules"
        custom_dir.mkdir()
        (custom_dir / "a.yml").write_text(yaml.dump({"anti_patterns": [{"id": "a1"}]}))
        (custom_dir / "b.yml").write_text(yaml.dump({"anti_patterns": [{"id": "b1"}]}))
        result = load_custom_rules(tmp_path)
        ids = {r["id"] for r in result.get("anti_patterns", [])}
        assert ids == {"a1", "b1"}

    def test_invalid_yaml_warning(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / ".ai-rules"
        custom_dir.mkdir()
        (custom_dir / "bad.yml").write_text(": : invalid yaml {{{")
        # Should not raise, just warn
        result = load_custom_rules(tmp_path)
        assert isinstance(result, dict)


class TestLoadCommonRules:
    """Tests for _load_common_rules()."""

    def test_with_common_security(self, tmp_path: Path) -> None:
        common = tmp_path / "common"
        common.mkdir()
        (common / "security.yml").write_text(yaml.dump({"anti_patterns": [{"id": "sec"}]}))
        result = _load_common_rules(tmp_path)
        assert "anti_patterns" in result

    def test_without_common_security(self, tmp_path: Path) -> None:
        result = _load_common_rules(tmp_path)
        assert result == {}


class TestGetEmbeddedRules:
    """Tests for _get_embedded_rules()."""

    def test_returns_fallback(self) -> None:
        result = _get_embedded_rules("python")
        assert result["language"] == "python"
        assert "anti_patterns" in result
        assert "naming_conventions" in result
        assert "complexity" in result
