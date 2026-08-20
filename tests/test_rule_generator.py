"""Coverage tests for rules_engine.rule_generator module (currently 14.2%)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from tools.scripts.rules_engine.rule_generator import (
    _EXT_TO_LANG,
    KNOWN_LANGUAGES,
    LANGUAGE_EXTENSIONS,
    detect_language_from_extension,
    format_rules,
    get_generated_rules_dir,
    list_generated_languages,
    load_generated_rules,
    save_rules,
    validate_rules_yaml,
)

# ─────────────────────────────────────────────────────────────
# Language detection
# ─────────────────────────────────────────────────────────────


def test_known_languages_not_empty():
    assert len(KNOWN_LANGUAGES) >= 30
    assert "python" in KNOWN_LANGUAGES
    assert "typescript" in KNOWN_LANGUAGES
    assert "rust" in KNOWN_LANGUAGES


def test_language_extensions_bidirectional():
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        for ext in exts:
            assert _EXT_TO_LANG[ext.lower()] == lang


def test_detect_language_from_extension():
    assert detect_language_from_extension("test.py") == "python"
    assert detect_language_from_extension("test.ts") == "typescript"
    assert detect_language_from_extension("test.rs") == "rust"
    assert detect_language_from_extension("test.go") == "go"
    assert detect_language_from_extension("test.unknown") is None
    assert detect_language_from_extension(Path("test.py")) == "python"


# ─────────────────────────────────────────────────────────────
# get_generated_rules_dir
# ─────────────────────────────────────────────────────────────


def test_get_generated_rules_dir_default(monkeypatch):
    monkeypatch.delenv("ADG_HOME", raising=False)
    dir_path = get_generated_rules_dir()
    assert dir_path.name == "generated"
    assert "adg" in str(dir_path)
    assert dir_path.is_absolute()


def test_get_generated_rules_dir_from_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    dir_path = get_generated_rules_dir()
    assert dir_path == tmp_path / "rules" / "generated"


# ─────────────────────────────────────────────────────────────
# format_rules
# ─────────────────────────────────────────────────────────────


def test_format_rules_basic():
    rules = [
        {
            "id": "python-test-rule",
            "name": "Test Rule",
            "severity": "warning",
            "category": "style",
            "pattern": r"bad_pattern",
            "message": "Avoid bad pattern",
            "fix_hint": "Use good pattern",
        }
    ]
    yaml_str = format_rules("python", rules)
    assert "language: python" in yaml_str
    assert "id: python-test-rule" in yaml_str
    assert "severity: warning" in yaml_str
    assert "fix_hint: Use good pattern" in yaml_str


def test_format_rules_multiple():
    rules = [
        {
            "id": "r1",
            "name": "R1",
            "severity": "error",
            "category": "sec",
            "pattern": "p1",
            "message": "m1",
        },
        {
            "id": "r2",
            "name": "R2",
            "severity": "info",
            "category": "style",
            "pattern": "p2",
            "message": "m2",
        },
    ]
    yaml_str = format_rules("python", rules)
    assert yaml_str.count("id: ") == 2


def test_format_rules_all_optional_fields():
    rules = [
        {
            "id": "full-rule",
            "name": "Full Rule",
            "severity": "error",
            "category": "security",
            "pattern": r"secret",
            "message": "Secret detected",
            "fix_hint": "Use env var",
            "exclude_files": ["config.py", "settings.py"],
            "exclude_patterns": ["test_*"],
            "test_cases": [{"code": "secret = 'x'", "should_match": True}],
        }
    ]
    yaml_str = format_rules("python", rules)
    assert "exclude_files:" in yaml_str
    assert "config.py" in yaml_str
    assert "test_cases:" in yaml_str


# ─────────────────────────────────────────────────────────────
# save_rules / load_generated_rules / discover_generated_rules
# ─────────────────────────────────────────────────────────────


def test_save_and_load_rules(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))

    rules = [
        {
            "id": "python-test",
            "name": "Test",
            "severity": "warning",
            "category": "style",
            "pattern": r"bad",
            "message": "Bad style",
        }
    ]

    path = save_rules("python", rules, force=True)
    assert path.exists()
    assert path.name == "anti_patterns.yml"
    assert "python" in path.parts

    loaded = load_generated_rules("python")
    assert len(loaded) == 1
    assert loaded[0]["id"] == "python-test"
    assert loaded[0]["severity"] == "warning"


def test_save_rules_force_overwrite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))

    rules1 = [
        {
            "id": "r1",
            "name": "R1",
            "severity": "error",
            "category": "c",
            "pattern": "p1",
            "message": "m1",
        }
    ]
    save_rules("python", rules1, force=True)

    rules2 = [
        {
            "id": "r2",
            "name": "R2",
            "severity": "warning",
            "category": "c",
            "pattern": "p2",
            "message": "m2",
        }
    ]
    save_rules("python", rules2, force=True)

    loaded = load_generated_rules("python")
    assert len(loaded) == 1
    assert loaded[0]["id"] == "r2"


def test_save_rules_rejects_unknown_language(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    rules = [
        {
            "id": "x",
            "name": "X",
            "severity": "error",
            "category": "c",
            "pattern": "p",
            "message": "m",
        }
    ]
    with pytest.raises(ValueError, match="Unknown language"):
        save_rules("unknown-lang", rules, force=True)


def test_save_rules_rejects_empty_rules(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    with pytest.raises(ValueError, match="At least one rule"):
        save_rules("python", [], force=True)


def test_load_generated_rules_nonexistent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    loaded = load_generated_rules("nonexistent")
    assert loaded == []


def test_discover_and_list_languages(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    rules = [
        {
            "id": "r1",
            "name": "R1",
            "severity": "error",
            "category": "c",
            "pattern": "p",
            "message": "m",
        }
    ]

    assert list_generated_languages() == []
    save_rules("python", rules, force=True)
    save_rules("rust", rules, force=True)

    discovered = list_generated_languages()
    assert "python" in discovered
    assert "rust" in discovered
    assert len(discovered) == 2


# ─────────────────────────────────────────────────────────────
# validate_rules_yaml
# ─────────────────────────────────────────────────────────────


def test_validate_rules_yaml_valid():
    content = """
language: python
anti_patterns:
  - id: test-rule
    name: Test Rule
    severity: warning
    category: style
    pattern: "bad"
    message: "Bad style"
"""
    errors = validate_rules_yaml(content)
    assert errors == []


def test_validate_rules_yaml_missing_language():
    content = """
anti_patterns:
  - id: test-rule
    name: Test Rule
    severity: warning
    category: style
    pattern: "bad"
    message: "Bad style"
"""
    errors = validate_rules_yaml(content)
    assert any("language" in e for e in errors)


def test_validate_rules_yaml_missing_anti_patterns():
    content = """
language: python
"""
    errors = validate_rules_yaml(content)
    assert any("anti_patterns" in e for e in errors)


def test_validate_rules_yaml_invalid_severity():
    content = """
language: python
anti_patterns:
  - id: test-rule
    name: Test Rule
    severity: critical
    category: style
    pattern: "bad"
    message: "Bad style"
"""
    errors = validate_rules_yaml(content)
    assert any("severity" in e for e in errors)


def test_validate_rules_yaml_invalid_regex():
    content = """
language: python
anti_patterns:
  - id: test-rule
    name: Test Rule
    severity: warning
    category: style
    pattern: "[invalid"
    message: "Bad style"
"""
    errors = validate_rules_yaml(content)
    assert any("invalid regex" in e for e in errors)


def test_validate_rules_yaml_duplicate_id():
    content = """
language: python
anti_patterns:
  - id: dup
    name: Rule 1
    severity: warning
    category: style
    pattern: "bad1"
    message: "Bad 1"
  - id: dup
    name: Rule 2
    severity: warning
    category: style
    pattern: "bad2"
    message: "Bad 2"
"""
    errors = validate_rules_yaml(content)
    assert any("Duplicate rule ID" in e for e in errors)


def test_validate_rules_yaml_missing_fields():
    content = """
language: python
anti_patterns:
  - id: incomplete
    name: Incomplete
    severity: warning
    # missing category, pattern, message
"""
    errors = validate_rules_yaml(content)
    assert len(errors) >= 3  # category, pattern, message


def test_validate_rules_yaml_empty_patterns():
    content = """
language: python
anti_patterns: []
"""
    errors = validate_rules_yaml(content)
    assert errors == []  # Empty list is valid


# ─────────────────────────────────────────────────────────────
# print_status (smoke test)
# ─────────────────────────────────────────────────────────────


def test_print_status_no_rules(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    from tools.scripts.rules_engine.rule_generator import print_status

    print_status()
    out = capsys.readouterr().out
    assert "No generated rules found" in out


def test_print_status_with_rules(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("ADG_HOME", str(tmp_path))
    from tools.scripts.rules_engine.rule_generator import print_status, save_rules

    rules = [
        {
            "id": "r1",
            "name": "R1",
            "severity": "error",
            "category": "c",
            "pattern": "p",
            "message": "m",
        }
    ]
    save_rules("python", rules, force=True)

    print_status()
    out = capsys.readouterr().out
    assert "python" in out
    assert "1 rules" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
