"""Tests for tools/scripts/check_rule_collisions.py."""

from __future__ import annotations

from pathlib import Path

import yaml

from tools.scripts.check_rule_collisions import build_report, main


def _write_rules(path: Path, rules: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"anti_patterns": rules}), encoding="utf-8")


def _common_rule(rule_id: str, pattern: str) -> dict[str, object]:
    return {"id": rule_id, "pattern": pattern, "message": "test", "severity": "error"}


def _language_rule(rule_id: str, pattern: str, supersedes: list[str] | None = None) -> dict[str, object]:
    rule: dict[str, object] = {
        "id": rule_id,
        "pattern": pattern,
        "message": "test",
        "severity": "error",
    }
    if supersedes is not None:
        rule["supersedes"] = supersedes
    return rule


def test_real_rules_have_no_collisions() -> None:
    report = build_report()
    assert report["duplicate_ids"] == {}
    assert report["unresolved_pattern_overlaps"] == []
    assert report.get("invalid_ids", []) == []


def test_detects_duplicate_rule_id(tmp_path: Path) -> None:
    _write_rules(tmp_path / "common" / "security.yml", [_common_rule("shared-id", "common")])
    _write_rules(
        tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml",
        [_language_rule("shared-id", "python")],
    )

    report = build_report(tmp_path)
    assert report["duplicate_ids"] == {"shared-id": ["common", "python"]}


def test_detects_undeclared_pattern_overlap(tmp_path: Path) -> None:
    _write_rules(tmp_path / "common" / "security.yml", [_common_rule("common-x", "same")])
    _write_rules(
        tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml",
        [_language_rule("py-x", "same")],
    )

    report = build_report(tmp_path)
    assert report["unresolved_pattern_overlaps"] == [{"source": "python", "rule_id": "py-x", "common_id": "common-x"}]


def test_declared_supersedes_suppresses_overlap(tmp_path: Path) -> None:
    _write_rules(tmp_path / "common" / "security.yml", [_common_rule("common-x", "same")])
    _write_rules(
        tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml",
        [_language_rule("py-x", "same", ["common-x"])],
    )

    report = build_report(tmp_path)
    assert report["unresolved_pattern_overlaps"] == []


def test_main_returns_nonzero_for_collision(tmp_path: Path) -> None:
    _write_rules(tmp_path / "common" / "security.yml", [_common_rule("shared-id", "common")])
    _write_rules(
        tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml",
        [_language_rule("shared-id", "python")],
    )

    assert main(["--root", str(tmp_path)]) == 1


def test_main_returns_zero_for_clean_tree(tmp_path: Path) -> None:
    _write_rules(tmp_path / "common" / "security.yml", [_common_rule("common-x", "common")])
    _write_rules(
        tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml",
        [_language_rule("py-x", "python")],
    )

    assert main(["--root", str(tmp_path)]) == 0


def test_detects_invalid_rule_ids(tmp_path: Path) -> None:
    _write_rules(
        tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml",
        [
            _language_rule("py-ok", "ok"),
            {"id": "", "pattern": "x", "message": "m", "severity": "error"},
            {"id": "bad id", "pattern": "y", "message": "m", "severity": "error"},
            {"pattern": "z", "message": "m", "severity": "error"},
        ],
    )

    report = build_report(tmp_path)
    reasons = [item["reason"] for item in report["invalid_ids"]]
    assert reasons == ["missing-or-empty-id", "whitespace-in-id", "missing-or-empty-id"]
    assert main(["--root", str(tmp_path)]) == 1
