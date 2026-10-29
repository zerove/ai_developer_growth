"""Smoke tests for Batch C language rules (Assembly/Fortran/GraphQL/MATLAB/Perl)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.validate_language_rules import validate_file


@pytest.mark.parametrize(
    ("language", "suffix", "expected_id"),
    [
        ("assembly", ".asm", "asm-todo"),
        ("fortran", ".f90", "for-todo"),
        ("graphql", ".graphql", "gql-todo"),
        ("matlab", ".m", "mcl-todo"),
        ("perl", ".pl", "pl-todo"),
    ],
)
def test_todo_rule_is_loaded(tmp_path: Path, language: str, suffix: str, expected_id: str) -> None:
    filepath = tmp_path / f"sample{suffix}"
    filepath.write_text("TODO\n", encoding="utf-8")

    result = validate_file(filepath, language)
    rule_ids = [issue.rule_id for issue in result.issues]

    assert expected_id in rule_ids
