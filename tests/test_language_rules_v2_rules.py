# 拆分自 tests/test_language_rules_v2.py

"""Tests for language rules v2 features: auto-fix, custom rules, reports, health score, linter aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from tools.scripts._common import file_hash_full as _file_hash
from tools.scripts.validate_language_rules import (
    _get_supported_files,
    _load_cache,
    _merge_rules,
    _save_cache,
    load_rules,
)


class TestCommonRules:
    def test_common_rules_loaded(self) -> None:
        """Verify common rules are merged into language rules."""
        rules = load_rules("python")
        anti_ids = [p["id"] for p in rules.get("anti_patterns", [])]
        # Common rules should be present
        assert any("common-" in rid for rid in anti_ids), f"Common rules not found in: {anti_ids[:10]}"

    def test_common_secret_rule(self) -> None:
        """Verify py-hardcoded-secret supersedes the common secret rule."""
        rules = load_rules("python")
        anti_ids = [p["id"] for p in rules.get("anti_patterns", [])]
        assert "py-hardcoded-secret" in anti_ids
        assert "common-hardcoded-secret" not in anti_ids


class TestSeverityOverride:
    def test_severity_override(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "test"},
            ],
        }
        custom = {
            "anti_patterns": [
                {"id": "py-test", "severity_override": "error"},
            ],
        }
        merged = _merge_rules(base, custom)
        assert merged["anti_patterns"][0]["severity"] == "error"
        assert merged["anti_patterns"][0]["pattern"] == "test"  # pattern preserved

    def test_severity_override_not_found(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "test"},
            ],
        }
        custom = {
            "anti_patterns": [
                {"id": "nonexistent", "severity_override": "error"},
            ],
        }
        merged = _merge_rules(base, custom)
        assert merged["anti_patterns"][0]["severity"] == "warning"  # unchanged


class TestCacheAndIncremental:
    def test_file_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        h1 = _file_hash(f)
        assert len(h1) == 64  # SHA-256 hex
        # Same content = same hash
        assert _file_hash(f) == h1
        # Changed content = different hash
        f.write_text("x = 2\n")
        assert _file_hash(f) != h1

    def test_file_hash_missing(self, tmp_path: Path) -> None:
        assert _file_hash(tmp_path / "nonexistent.py") == ""

    def test_load_save_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / ".rule-cache"
        _save_cache(cache_file, {"a.py": "hash1", "b.py": "hash2"})
        loaded = _load_cache(cache_file)
        assert loaded["a.py"] == "hash1"
        assert loaded["b.py"] == "hash2"

    def test_load_cache_missing(self, tmp_path: Path) -> None:
        assert _load_cache(tmp_path / "nonexistent") == {}

    def test_get_supported_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x=1")
        (tmp_path / "b.rs").write_text("fn main() {}")
        (tmp_path / "c.txt").write_text("hello")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "d.py").write_text("ignored")
        files = _get_supported_files(tmp_path, [".git"])
        names = [f.name for f in files]
        assert "a.py" in names
        assert "b.rs" in names
        assert "c.txt" not in names
        assert "d.py" not in names
