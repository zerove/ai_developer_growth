"""Tests for rule test framework, fix generator, and marketplace CLI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from generate_fixes import apply_fixes_to_yaml, generate_fixes, heuristic_fix
from rule_catalog import BUILTIN_PACKS
from rule_catalog import matches as _matches
from validate_rule_tests import validate_rule_tests

# ──────────────────────────────────────────────────────────
# Rule test framework tests
# ──────────────────────────────────────────────────────────


class TestRuleTestFramework:
    def test_python_rules_have_tests(self) -> None:
        passed, failed, errors = validate_rule_tests("python")
        assert passed > 0, "No Python test cases found"
        assert failed == 0, f"Failed tests: {errors}"

    def test_typescript_rules_have_tests(self) -> None:
        passed, failed, errors = validate_rule_tests("typescript")
        assert passed > 0, "No TypeScript test cases found"
        assert failed == 0, f"Failed tests: {errors}"

    def test_nonexistent_lang(self) -> None:
        passed, failed, errors = validate_rule_tests("nonexistent")
        assert passed == 0
        assert failed == 0
        assert len(errors) > 0

    def test_zig_no_tests(self) -> None:
        """Zig has no test_cases yet - should report 0 passed."""
        passed, failed, errors = validate_rule_tests("zig")
        assert passed == 0
        assert failed == 0


# ──────────────────────────────────────────────────────────
# Heuristic fix generator tests
# ──────────────────────────────────────────────────────────


class TestHeuristicFix:
    def test_eval_exec(self) -> None:
        fix = heuristic_fix({"pattern": "\\beval\\s*\\(", "message": "eval"})
        assert "literal_eval" in fix["fix_replacement"]

    def test_bare_except(self) -> None:
        fix = heuristic_fix({"pattern": "except\\s*:", "message": "bare except"})
        assert "Exception" in fix["fix_replacement"]

    def test_sql_injection(self) -> None:
        fix = heuristic_fix({"pattern": "", "message": "SQL string formatting injection"})
        assert "execute" in fix["fix_replacement"]

    def test_console_log(self) -> None:
        fix = heuristic_fix({"pattern": "", "message": "Remove console.log"})
        assert fix["source"] == "heuristic"

    def test_fix_hint_fallback(self) -> None:
        fix = heuristic_fix({"pattern": "unknown_pattern", "message": "unknown", "fix_hint": "Use safer approach"})
        assert "safer" in fix["fix_replacement"]

    def test_no_match_returns_none(self) -> None:
        fix = heuristic_fix({"pattern": "xyzzy", "message": "nothing matches"})
        assert fix["source"] == "none"


class TestGenerateFixes:
    def test_generate_for_python(self) -> None:
        fixes = generate_fixes(["python"])
        assert len(fixes) > 0
        # All should have required fields
        for f in fixes:
            assert "id" in f
            assert "fix_replacement" in f
            assert "source" in f

    def test_generate_for_all(self) -> None:
        fixes = generate_fixes(["python", "typescript"])
        assert len(fixes) > 20

    def test_apply_dry_run(self) -> None:
        fixes = [{"file": "test.yml", "id": "x", "fix_replacement": "y"}]
        applied = apply_fixes_to_yaml(fixes, dry_run=True)
        assert applied == 1


# ──────────────────────────────────────────────────────────
# Marketplace tests
# ──────────────────────────────────────────────────────────


class TestMarketplace:
    def test_builtin_packs_exist(self) -> None:
        assert "security" in BUILTIN_PACKS
        assert "python-pack" in BUILTIN_PACKS
        assert "full" in BUILTIN_PACKS

    def test_pack_structure(self) -> None:
        for pack_id, info in BUILTIN_PACKS.items():
            assert "name" in info, f"{pack_id} missing name"
            assert "description" in info, f"{pack_id} missing description"
            assert "source" in info, f"{pack_id} missing source"
            assert "rule_count" in info, f"{pack_id} missing rule_count"

    def test_matches_sql(self) -> None:
        rule = {"id": "py-sql-injection", "message": "SQL injection via string concat", "pattern": "SELECT.*\\+"}
        assert _matches(rule, "sql")

    def test_matches_id(self) -> None:
        rule = {"id": "py-bare-except", "message": "Bare except", "pattern": ""}
        assert _matches(rule, "bare-except")

    def test_no_match(self) -> None:
        rule = {"id": "py-bare-except", "message": "Bare except", "pattern": ""}
        assert not _matches(rule, "xyzzy")
