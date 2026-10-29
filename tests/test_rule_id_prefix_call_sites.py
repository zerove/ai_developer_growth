from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.scripts.complexity_analyzer import (
    _check_file_length,
    _check_function_length,
    _check_line_length,
)
from tools.scripts.naming_analyzer import _check_filename, _check_identifier_kind
from tools.scripts.validate_language_rules import (
    check_naming_conventions,
    check_thresholds,
    load_rules,
)

CASES = [
    ("rust", "rs"),
    ("java", "java"),
    ("javascript", "js"),
    ("ruby", "rb"),
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


@pytest.mark.parametrize(("language", "prefix"), CASES)
def test_public_checks_use_canonical_prefix(language: str, prefix: str) -> None:
    rules = load_rules(language)
    naming_ids = {issue.rule_id for issue in check_naming_conventions(["BadName"], rules, "test.txt")}
    threshold_ids = {issue.rule_id for issue in check_thresholds(["x" * 130], rules, "test.txt")}

    assert f"{prefix}-naming-file" in naming_ids
    assert f"{prefix}-threshold-line-length" in threshold_ids


def test_rule_sources_do_not_truncate_language_names() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source_root = repo_root / "tools" / "scripts"
    truncation = re.compile(r"\b(?:language|lang)\s*\[\s*:\s*2\s*\]")
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if truncation.search(line):
                violations.append(f"{path.relative_to(repo_root)}:{line_number}: {line.strip()}")
    assert not violations, "\n".join(violations)
