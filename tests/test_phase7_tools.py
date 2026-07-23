"""Tests for Phase 7 tools: registry, author, tracker, git-diff, visualize, editor."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from rule_registry import (
    _load_registry,
    _save_registry,
    _file_hash,
    init_registry,
    _registry_dir,
    _packs_dir,
)
from rule_author import TEMPLATES, SEVERITY_LEVELS, CATEGORY_TYPES
from rule_tracker import _count_by_severity, _count_by_rule
from git_diff_incremental import get_incremental_files, filter_supported_files


# ──────────────────────────────────────────────────────────
# Rule Registry tests
# ──────────────────────────────────────────────────────────


class TestRuleRegistry:
    def test_file_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.yml"
        f.write_text("test: 1")
        h = _file_hash(f)
        assert len(h) == 16  # SHA256 truncated
        assert _file_hash(f) == h  # Same content = same hash

    def test_save_load_registry(self, tmp_path: Path) -> None:
        data = {"packs": {"my-pack": {"version": "1.0"}}, "version": "1.0"}
        reg_file = tmp_path / "registry.json"
        # Patch temporarily
        import rule_registry
        old = rule_registry._registry_file
        rule_registry._registry_file = lambda: reg_file
        try:
            _save_registry(data)
            loaded = _load_registry()
            assert loaded["packs"]["my-pack"]["version"] == "1.0"
        finally:
            rule_registry._registry_file = old

    def test_templates_exist(self) -> None:
        assert "anti_patterns" in TEMPLATES
        assert "naming_conventions" in TEMPLATES
        assert "complexity" in TEMPLATES

    def test_severity_levels(self) -> None:
        assert "error" in SEVERITY_LEVELS
        assert "warning" in SEVERITY_LEVELS
        assert "info" in SEVERITY_LEVELS

    def test_category_types(self) -> None:
        assert "security" in CATEGORY_TYPES
        assert "code_quality" in CATEGORY_TYPES


# ──────────────────────────────────────────────────────────
# Rule Tracker tests
# ──────────────────────────────────────────────────────────


class TestRuleTracker:
    def test_count_by_severity(self) -> None:
        results = [
            {"issues": [{"severity": "error"}, {"severity": "warning"}, {"severity": "error"}]},
            {"issues": [{"severity": "info"}]},
        ]
        counts = _count_by_severity(results)
        assert counts["error"] == 2
        assert counts["warning"] == 1
        assert counts["info"] == 1

    def test_count_by_rule(self) -> None:
        results = [
            {"issues": [{"rule_id": "py-bare-except"}, {"rule_id": "py-bare-except"}]},
            {"issues": [{"rule_id": "py-eval"}]},
        ]
        counts = _count_by_rule(results)
        assert counts["py-bare-except"] == 2
        assert counts["py-eval"] == 1

    def test_empty_results(self) -> None:
        assert _count_by_severity([]) == {}
        assert _count_by_rule([]) == {}


# ──────────────────────────────────────────────────────────
# Git Diff Incremental tests
# ──────────────────────────────────────────────────────────


class TestGitDiffIncremental:
    def test_filter_supported_files(self, tmp_path: Path) -> None:
        files = [
            tmp_path / "a.py",
            tmp_path / "b.rs",
            tmp_path / "c.txt",
            tmp_path / "d.js",
        ]
        for f in files:
            f.write_text("x")
        filtered = filter_supported_files(files)
        names = [f.name for f in filtered]
        assert "a.py" in names
        assert "b.rs" in names
        assert "d.js" in names
        assert "c.txt" not in names

    def test_incremental_in_repo(self) -> None:
        """Test that get_incremental_files works in the actual repo."""
        files = get_incremental_files(
            repo_dir=str(Path(__file__).parent.parent),
            ref="HEAD~1",
        )
        # Should return some files (recent commits changed files)
        assert isinstance(files, list)

    def test_unsupported_extensions_filtered(self, tmp_path: Path) -> None:
        files = [
            tmp_path / "readme.md",
            tmp_path / "data.json",
            tmp_path / "config.xml",
        ]
        for f in files:
            f.write_text("x")
        filtered = filter_supported_files(files)
        assert len(filtered) == 0


# ──────────────────────────────────────────────────────────
# Rule Visualize / Editor imports
# ──────────────────────────────────────────────────────────


class TestWebTools:
    def test_visualize_imports(self) -> None:
        from rule_visualize import get_all_rules
        rules = get_all_rules()
        assert len(rules) > 0
        assert "python" in rules
        assert rules["python"]["total"] > 0

    def test_editor_html_exists(self) -> None:
        from rule_editor import HTML
        assert "Rule Editor" in HTML
        assert "yaml-editor" in HTML
