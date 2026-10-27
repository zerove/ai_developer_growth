"""Tests for language rules v2 features: auto-fix, custom rules, reports, health score, linter aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


from tools.scripts.validate_language_rules import (
    FixResult,
    Issue,
    _merge_rules,
    apply_fixes,
    load_custom_rules,
    validate_file,
)


class TestFixResult:
    def test_creation(self) -> None:
        fix = FixResult(
            file="test.py",
            rule_id="py-test",
            line=1,
            original="old",
            fixed="new",
            description="Fixed it",
        )
        assert fix.file == "test.py"
        assert fix.original == "old"
        assert fix.fixed == "new"

    def test_to_dict(self) -> None:
        fix = FixResult(
            file="test.py",
            rule_id="py-test",
            line=5,
            original="print('hello')",
            fixed="logger.info('hello')",
            description="Use logging",
        )
        d = fix.to_dict()
        assert d["file"] == "test.py"
        assert d["line"] == 5
        assert d["original"] == "print('hello')"


class TestAutoFix:
    # ADR-072: 夹具原为顶格裸 ``except:``, **本身就不是合法 Python**
    # (except 必须跟在 try 之后)。旧实现无条件写盘, 该用例一直是绿的,
    # 实际在验证“把一份非法文件改成另一份非法文件”。加上写盘兜底后它
    # 转红, 这正是兜底生效的证据 —— 故修夹具, 而非放宽兜底去迁就非法输入。
    VALID_BARE_EXCEPT = "try:\n    pass\nexcept:\n    pass\n"

    def _bare_except_issue(self, test_file: Path) -> list:  # noqa: ANN205
        return [
            Issue(
                rule_id="py-bare-except",
                severity="error",
                category="error_handling",
                file=str(test_file),
                line=3,
                message="Avoid bare except",
                fix_replacement="s/except:/except Exception:/",
            )
        ]

    def test_apply_fixes_dry_run(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text(self.VALID_BARE_EXCEPT)

        fixes = apply_fixes(test_file, self._bare_except_issue(test_file), dry_run=True)
        assert len(fixes) == 1
        assert fixes[0].fixed == "except Exception:"
        # File should NOT be modified in dry run
        assert test_file.read_text() == self.VALID_BARE_EXCEPT

    def test_apply_fixes_real(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text(self.VALID_BARE_EXCEPT)

        fixes = apply_fixes(test_file, self._bare_except_issue(test_file), dry_run=False)
        assert len(fixes) == 1
        # File SHOULD be modified
        assert "except Exception:" in test_file.read_text()

    def test_apply_fixes_no_replacement(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        issues = [
            Issue(
                rule_id="py-test",
                severity="warning",
                category="general",
                file=str(test_file),
                line=1,
                message="Some issue",
                fix_replacement="",
            )
        ]

        fixes = apply_fixes(test_file, issues, dry_run=True)
        assert len(fixes) == 0

    def test_apply_fixes_out_of_range_line(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        issues = [
            Issue(
                rule_id="py-test",
                severity="warning",
                category="general",
                file=str(test_file),
                line=999,
                message="Some issue",
                fix_replacement="s/x/y/",
            )
        ]

        fixes = apply_fixes(test_file, issues, dry_run=True)
        assert len(fixes) == 0


class TestCustomRules:
    def test_load_custom_rules_empty(self, tmp_path: Path) -> None:
        rules = load_custom_rules(tmp_path)
        assert rules["anti_patterns"] == []

    def test_load_custom_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        rule_file = rules_dir / "custom.yml"
        rule_file.write_text(
            yaml.dump(
                {
                    "anti_patterns": [
                        {
                            "id": "custom-no-todo",
                            "name": "TODO comments",
                            "severity": "warning",
                            "category": "code_quality",
                            "pattern": "TODO|FIXME",
                            "message": "Avoid TODO comments",
                        }
                    ]
                }
            )
        )

        rules = load_custom_rules(tmp_path)
        assert len(rules["anti_patterns"]) == 1
        assert rules["anti_patterns"][0]["id"] == "custom-no-todo"

    def test_merge_rules_override(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "old"},
            ],
            "thresholds": {"max_line_length": 120},
        }
        custom = {
            "anti_patterns": [
                {"id": "py-test", "severity": "error", "pattern": "new"},
            ],
            "thresholds": {"max_line_length": 100},
        }

        merged = _merge_rules(base, custom)
        # Should override by ID
        assert merged["anti_patterns"][0]["severity"] == "error"
        assert merged["anti_patterns"][0]["pattern"] == "new"
        # Should override threshold
        assert merged["thresholds"]["max_line_length"] == 100

    def test_merge_rules_append_new(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "old"},
            ]
        }
        custom = {
            "anti_patterns": [
                {"id": "custom-new", "severity": "info", "pattern": "new"},
            ]
        }

        merged = _merge_rules(base, custom)
        assert len(merged["anti_patterns"]) == 2
        assert merged["anti_patterns"][1]["id"] == "custom-new"

    def test_validate_file_with_custom_rules(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1  # TODO: fix this\n")

        custom = {
            "anti_patterns": [
                {
                    "id": "custom-no-todo",
                    "name": "TODO comments",
                    "severity": "warning",
                    "category": "code_quality",
                    "pattern": "TODO|FIXME",
                    "message": "Avoid TODO comments",
                }
            ]
        }

        result = validate_file(test_file, "python", custom_rules=custom)
        todo_issues = [i for i in result.issues if i.rule_id == "custom-no-todo"]
        assert len(todo_issues) == 1
