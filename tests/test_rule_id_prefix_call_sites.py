from __future__ import annotations

import pytest

from tools.scripts.complexity_analyzer import (
    _check_file_length,
    _check_function_length,
    _check_line_length,
)
from tools.scripts.naming_analyzer import _check_filename, _check_identifier_kind

CASES = [
    ("rust", "rs"),
    ("java", "java"),
    ("javascript", "js"),
    ("ruby", "ruby"),
    ("typescript", "ts"),
]


@pytest.mark.parametrize(("language", "prefix"), CASES)
def test_threshold_rule_ids_use_canonical_prefix(language: str, prefix: str) -> None:
    line_issues = _check_line_length(["x" * 130], "test.txt", language, 120)
    file_issues = _check_file_length(["x"] * 10, "test.txt", language, 5)
    function_issues = _check_function_length([("f", 1, 3)], "test.txt", language, 1, 10, ["x"] * 3)

    assert [issue.rule_id for issue in line_issues] == [f"{prefix}-threshold-line-length"]
    assert [issue.rule_id for issue in file_issues] == [f"{prefix}-threshold-file-length"]
    assert [issue.rule_id for issue in function_issues] == [f"{prefix}-threshold-func-length"]


@pytest.mark.parametrize(("language", "prefix"), CASES)
def test_naming_file_rule_ids_use_canonical_prefix(language: str, prefix: str) -> None:
    issues = _check_filename("BadName.rs", language, {"file": {"pattern": r"^[a-z]"}})

    assert [issue.rule_id for issue in issues] == [f"{prefix}-naming-file"]


def test_naming_identifier_rule_id_uses_canonical_prefix() -> None:
    issues = _check_identifier_kind(
        ["fn BadName() {"],
        "rust",
        "function",
        {"pattern": r"^[a-z][a-z0-9_]*$"},
        "test.rs",
    )

    assert [issue.rule_id for issue in issues] == ["rs-naming-function"]
