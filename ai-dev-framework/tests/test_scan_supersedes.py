from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ai_dev_framework import scan as scan_mod  # noqa: E402

LANGUAGE_RULES = r"""
anti_patterns:
  - id: py-eval-exec
    pattern: '\beval\s*\('
    supersedes: [common-eval-exec]
"""

COMMON_RULES = r"""
anti_patterns:
  - id: common-eval-exec
    pattern: '\beval\s*\('
  - id: common-hardcoded-secret
    pattern: 'password'
"""


def _write_rules(root: Path, language: str, common: str) -> None:
    language_path = root / "rules" / "languages" / "python" / "rules.d" / "anti_patterns.yml"
    language_path.parent.mkdir(parents=True)
    language_path.write_text(language, encoding="utf-8")
    common_path = root / "rules" / "common" / "security.yml"
    common_path.parent.mkdir(parents=True)
    common_path.write_text(common, encoding="utf-8")


def _load_with_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    common: str,
) -> list[dict[str, object]]:
    rules_home = tmp_path / "adg"
    _write_rules(rules_home, language, common)
    monkeypatch.setattr(scan_mod, "_RULES_HOME", rules_home)
    monkeypatch.setattr(scan_mod, "_PROJECT_LANGUAGES", tmp_path / "missing")
    return scan_mod._load_rules_for_language("python")


def test_language_rule_supersedes_common_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules = _load_with_rules(tmp_path, monkeypatch, LANGUAGE_RULES, COMMON_RULES)
    ids = [rule["id"] for rule in rules]
    assert "py-eval-exec" in ids
    assert "common-eval-exec" not in ids
    assert "common-hardcoded-secret" in ids


def test_common_rule_kept_without_supersedes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    language = r"""
anti_patterns:
  - id: py-eval-exec
    pattern: '\beval\s*\('
"""
    rules = _load_with_rules(tmp_path, monkeypatch, language, COMMON_RULES)
    ids = [rule["id"] for rule in rules]
    assert "py-eval-exec" in ids
    assert "common-eval-exec" in ids


def test_scan_file_reports_eval_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules = _load_with_rules(tmp_path, monkeypatch, LANGUAGE_RULES, COMMON_RULES)
    assert [rule["id"] for rule in rules].count("py-eval-exec") == 1

    target = tmp_path / "target.py"
    target.write_text("result = eval(user_input)\n", encoding="utf-8")
    result = scan_mod.scan_file(target)
    assert [issue.rule_id for issue in result.issues] == ["py-eval-exec"]
