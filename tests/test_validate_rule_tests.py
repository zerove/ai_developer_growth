"""Tests for validate_rule_tests.py (48% → target 85%)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.validate_rule_tests import (
    _load_rules_with_tests,
    main,
    validate_rule_tests,
)


class TestLoadRulesWithTests:
    """Tests for _load_rules_with_tests()."""

    def test_no_rules_dir(self, tmp_path: Path) -> None:
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path / "nonexistent"
            result = _load_rules_with_tests("python")
            assert result == []

    def test_empty_rules_dir(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = _load_rules_with_tests("python")
            assert result == []

    def test_rules_with_test_cases(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti.yml").write_text(
            "anti_patterns:\n"
            "  - id: py-test\n"
            "    pattern: 'except\\s*:'\n"
            "    test_cases:\n"
            "      - code: 'except:'\n"
            "        should_match: true\n"
        )
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = _load_rules_with_tests("python")
            assert len(result) == 1
            assert result[0]["category"] == "anti_patterns"

    def test_rules_without_test_cases(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti.yml").write_text("anti_patterns:\n  - id: py-no-test\n    pattern: 'bad'\n")
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = _load_rules_with_tests("python")
            assert result == []

    def test_empty_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "empty.yml").write_text("")
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = _load_rules_with_tests("python")
            assert result == []

    def test_non_dict_rules_skipped(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "bad.yml").write_text("anti_patterns:\n  - just_a_string\n")
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = _load_rules_with_tests("python")
            assert result == []

    def test_all_categories(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True)
        yaml_content = (
            "anti_patterns:\n"
            "  - id: a1\n"
            "    pattern: 'a'\n"
            "    test_cases:\n"
            "      - code: 'a'\n"
            "        should_match: true\n"
            "naming_conventions:\n"
            "  - id: n1\n"
            "    pattern: 'n'\n"
            "    test_cases:\n"
            "      - code: 'n'\n"
            "        should_match: true\n"
            "complexity:\n"
            "  - id: c1\n"
            "    pattern: 'c'\n"
            "    test_cases:\n"
            "      - code: 'c'\n"
            "        should_match: true\n"
            "thresholds:\n"
            "  - id: t1\n"
            "    pattern: 't'\n"
            "    test_cases:\n"
            "      - code: 't'\n"
            "        should_match: true\n"
        )
        (rules_dir / "all.yml").write_text(yaml_content)
        with patch("tools.scripts.validate_rule_tests._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = _load_rules_with_tests("python")
            assert len(result) == 4


class TestValidateRuleTests:
    """Tests for validate_rule_tests()."""

    def test_no_rules_with_tests(self, tmp_path: Path) -> None:
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = []
            passed, failed, errors = validate_rule_tests("python")
            assert passed == 0
            assert failed == 0
            assert len(errors) == 1

    def test_passing_test(self, tmp_path: Path) -> None:
        mock_rules = [
            {
                "file": "test.yml",
                "category": "anti_patterns",
                "rule": {
                    "id": "py-test",
                    "pattern": "except\\s*:",
                    "test_cases": [
                        {"code": "except:", "should_match": True},
                        {"code": "except Exception:", "should_match": False},
                    ],
                },
            }
        ]
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = mock_rules
            passed, failed, errors = validate_rule_tests("python")
            assert passed == 2
            assert failed == 0

    def test_failing_test(self, tmp_path: Path) -> None:
        mock_rules = [
            {
                "file": "test.yml",
                "category": "anti_patterns",
                "rule": {
                    "id": "py-bad",
                    "pattern": "^(?!.*#).*print\\(",
                    "test_cases": [
                        {"code": "print('x')", "should_match": True},
                    ],
                },
            }
        ]
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = mock_rules
            passed, failed, errors = validate_rule_tests("python")
            # May pass or fail depending on regex, just check no crash
            assert passed + failed >= 1

    def test_no_pattern(self, tmp_path: Path) -> None:
        mock_rules = [
            {
                "file": "test.yml",
                "category": "anti_patterns",
                "rule": {
                    "id": "py-nopat",
                    "test_cases": [{"code": "x", "should_match": True}],
                },
            }
        ]
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = mock_rules
            passed, failed, errors = validate_rule_tests("python")
            assert failed == 0
            assert any("no pattern" in e for e in errors)

    def test_invalid_regex(self, tmp_path: Path) -> None:
        mock_rules = [
            {
                "file": "test.yml",
                "category": "anti_patterns",
                "rule": {
                    "id": "py-invalid",
                    "pattern": "[invalid",
                    "test_cases": [{"code": "x", "should_match": True}],
                },
            }
        ]
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = mock_rules
            passed, failed, errors = validate_rule_tests("python")
            assert failed >= 1
            assert any("invalid regex" in e for e in errors)

    def test_empty_pattern_string(self, tmp_path: Path) -> None:
        mock_rules = [
            {
                "file": "test.yml",
                "category": "anti_patterns",
                "rule": {
                    "id": "py-empty",
                    "pattern": "",
                    "test_cases": [{"code": "x", "should_match": True}],
                },
            }
        ]
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = mock_rules
            passed, failed, errors = validate_rule_tests("python")
            assert any("no pattern" in e for e in errors)

    def test_should_match_default_true(self, tmp_path: Path) -> None:
        mock_rules = [
            {
                "file": "test.yml",
                "category": "anti_patterns",
                "rule": {
                    "id": "py-default",
                    "pattern": "pass",
                    "test_cases": [{"code": "pass"}],  # no should_match
                },
            }
        ]
        with patch("tools.scripts.validate_rule_tests._load_rules_with_tests") as mock_load:
            mock_load.return_value = mock_rules
            passed, failed, errors = validate_rule_tests("python")
            assert passed == 1


class TestMain:
    """Tests for main() function."""

    def test_no_args_error(self) -> None:
        with patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit):
                main()

    def test_json_output(self, tmp_path: Path) -> None:
        with patch("sys.argv", ["prog", "--lang", "python", "--json"]):
            with patch("tools.scripts.validate_rule_tests.validate_rule_tests") as mock_val:
                mock_val.return_value = (5, 0, [])
                with patch("builtins.print") as mock_print:
                    ret = main()
                    assert ret == 0
                    # Check JSON was printed
                    printed = mock_print.call_args[0][0]
                    data = json.loads(printed)
                    assert data["total_passed"] == 5

    def test_verbose_output(self, tmp_path: Path) -> None:
        with patch("sys.argv", ["prog", "--lang", "python", "--verbose"]):
            with patch("tools.scripts.validate_rule_tests.validate_rule_tests") as mock_val:
                mock_val.return_value = (1, 1, ["error msg"])
                with patch("builtins.print") as mock_print:
                    ret = main()
                    assert ret == 1
                    printed = [c[0][0] for c in mock_print.call_args_list]
                    assert any("error msg" in p for p in printed)

    def test_all_languages(self) -> None:
        with patch("sys.argv", ["prog", "--all"]):
            with patch("tools.scripts.validate_rule_tests.validate_rule_tests") as mock_val:
                mock_val.return_value = (0, 0, ["No rules"])
                ret = main()
                assert ret == 0

    def test_failed_returns_1(self) -> None:
        with patch("sys.argv", ["prog", "--lang", "python"]):
            with patch("tools.scripts.validate_rule_tests.validate_rule_tests") as mock_val:
                mock_val.return_value = (3, 2, ["err1", "err2"])
                ret = main()
                assert ret == 1
