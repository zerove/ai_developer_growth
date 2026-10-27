"""adg_cli Issue 适配器与 rules_engine 规范 Issue 的字段一致性。"""

from __future__ import annotations

from tools.scripts.adg_cli.core import Issue as CliIssue
from tools.scripts.rules_engine.models import Issue as CanonicalIssue


def test_cli_issue_is_a_canonical_issue() -> None:
    issue = CliIssue("r1", "error", "security", "f.py", 3, 7, "msg", "fix")

    assert isinstance(issue, CanonicalIssue)


def test_legacy_positional_order_maps_to_canonical_fields() -> None:
    issue = CliIssue("r1", "error", "security", "f.py", 3, 7, "msg", "fix")

    assert issue.rule_id == "r1"
    assert issue.severity == "error"
    assert issue.category == "security"
    assert issue.file == "f.py"
    assert issue.line == 3
    assert issue.column == 7
    assert issue.message == "msg"
    assert issue.fix_hint == "fix"
    assert issue.explanation == ""
    assert issue.context_role == ""
    assert issue.fix_replacement == ""
    assert issue.related_docs == []


def test_to_dict_matches_canonical_model() -> None:
    cli_issue = CliIssue("r1", "error", "security", "f.py", 3, 7, "msg", "fix")
    canonical_issue = CanonicalIssue(
        rule_id="r1",
        severity="error",
        category="security",
        file="f.py",
        line=3,
        message="msg",
        fix_hint="fix",
        column=7,
    )

    assert cli_issue.to_dict() == canonical_issue.to_dict()


def test_related_docs_survive_serialization() -> None:
    docs = [{"title": "规则说明", "url": "https://example.com/rule"}]
    issue = CliIssue("r1", "error", "security", "f.py", 1, 1, "msg", "", docs)

    assert issue.related_docs == docs
    assert issue.to_dict()["related_docs"] == docs
