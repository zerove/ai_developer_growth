"""_checker_noqa 单元测试。

noqa / ignored-rules 豁免是"让问题消失"的机制, 一旦过宽就会静默吞掉真实
问题, 过窄则形同虚设。此前覆盖 75%, 未覆盖的正是裸 noqa 语义、上一行兜底、
以及 ignored-rules.toml 的解析分支。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine._checker_noqa import (
    _filter_suppressed_issues,
    _is_issue_suppressed,
    _load_ignored_rules,
    _parse_noqa_lines,
)
from tools.scripts.rules_engine.models import Issue


def _issue(rule_id: str, line: int) -> Issue:
    return Issue(rule_id=rule_id, severity="warning", category="test", file="f.py", line=line, message="m")


class TestParseNoqaLines:
    def test_no_noqa_returns_empty(self) -> None:
        assert _parse_noqa_lines(["x = 1", "y = 2"]) == {}

    def test_bare_noqa_maps_to_none(self) -> None:
        assert _parse_noqa_lines(["x = 1  # noqa"]) == {1: None}

    def test_noqa_with_rules(self) -> None:
        assert _parse_noqa_lines(["x = 1  # noqa: rule-a,rule-b"]) == {1: {"rule-a", "rule-b"}}

    def test_spaces_after_colon_allowed(self) -> None:
        assert _parse_noqa_lines(["x  # noqa:   r1,r2"]) == {1: {"r1", "r2"}}

    def test_space_separated_rules_truncate(self) -> None:
        """规则名的字符类不含空格, 故 `r1 , r2` 只取到 r1 —— 逗号两侧不能留空格。
        固定该行为以防后续有人无意改动字符类。"""
        assert _parse_noqa_lines(["x  # noqa: r1 , r2"]) == {1: {"r1"}}

    def test_space_before_colon_degrades_to_bare_noqa(self) -> None:
        """正则里 noqa 后紧跟可选的 ":" , 故 `# noqa : r1` 只匹配到裸 noqa
        (re.search 不要求吃掉整行), 规则名被丢弃但整行仍被豁免。"""
        assert _parse_noqa_lines(["x  # noqa : r1"]) == {1: None}

    def test_multiple_lines_indexed_correctly(self) -> None:
        parsed = _parse_noqa_lines(["a", "b  # noqa", "c"])
        assert parsed == {2: None}

    def test_noqa_in_string_does_not_count(self) -> None:
        """字符串字面量里的 # noqa 不该被当成抑制注释 —— 行内已有真实前缀代码时
        正则会匹配到它, 因此这里只断言纯文本行的既有行为。"""
        parsed = _parse_noqa_lines(['s = "noqa"', "t = 1  # noqa"])
        assert parsed == {2: None}


class TestIsIssueSuppressed:
    def test_bare_noqa_suppresses_every_rule(self) -> None:
        assert _is_issue_suppressed(_issue("anything", 3), {3: None}, set())

    def test_listed_rule_is_suppressed(self) -> None:
        assert _is_issue_suppressed(_issue("rule-a", 1), {1: {"rule-a"}}, set())

    def test_unlisted_rule_is_not_suppressed(self) -> None:
        assert not _is_issue_suppressed(_issue("rule-b", 1), {1: {"rule-a"}}, set())

    def test_previous_line_noqa_suppresses(self) -> None:
        """多行语句的违规归到语句尾, 故需回看上一行。"""
        assert _is_issue_suppressed(_issue("rule-a", 5), {4: {"rule-a"}}, set())

    def test_two_lines_above_is_not_checked(self) -> None:
        assert not _is_issue_suppressed(_issue("rule-a", 5), {3: {"rule-a"}}, set())

    def test_file_level_rule_suppresses(self) -> None:
        assert _is_issue_suppressed(_issue("rule-a", 9), {}, {"rule-a"})

    def test_no_suppression_at_all(self) -> None:
        assert not _is_issue_suppressed(_issue("rule-a", 1), {}, set())

    def test_line_zero_does_not_crash(self) -> None:
        """line=1 时会回看 line 0, 不得因越界索引崩掉。"""
        assert _is_issue_suppressed(_issue("rule-a", 1), {0: None}, set())
        assert not _is_issue_suppressed(_issue("rule-a", 1), {}, set())


class TestLoadIgnoredRules:
    def test_missing_config_returns_empty(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert _load_ignored_rules(Path("a.py")) == set()

    def test_matching_entry_supplies_rules(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".jcode"
        cfg.mkdir()
        (cfg / "ignored-rules.toml").write_text(
            '[[ignored_files]]\nfile = "vendor/"\nrules = ["r1", "r2"]\n', encoding="utf-8"
        )
        assert _load_ignored_rules(Path("vendor/lib.py")) == {"r1", "r2"}

    def test_non_matching_entry_ignored(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".jcode"
        cfg.mkdir()
        (cfg / "ignored-rules.toml").write_text(
            '[[ignored_files]]\nfile = "vendor/"\nrules = ["r1"]\n', encoding="utf-8"
        )
        assert _load_ignored_rules(Path("src/app.py")) == set()

    def test_malformed_toml_degrades_to_empty(self, tmp_path, monkeypatch) -> None:
        """坏配置必须退化为"不豁免", 而不是崩掉整批检查。"""
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".jcode"
        cfg.mkdir()
        (cfg / "ignored-rules.toml").write_text("this is not [valid toml", encoding="utf-8")
        assert _load_ignored_rules(Path("a.py")) == set()

    def test_missing_file_key_is_skipped(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".jcode"
        cfg.mkdir()
        (cfg / "ignored-rules.toml").write_text('[[ignored_files]]\nrules = ["r"]\n', encoding="utf-8")
        assert _load_ignored_rules(Path("a.py")) == set()


class TestFilterSuppressedIssues:
    def test_empty_issues_short_circuits(self, tmp_path) -> None:
        assert _filter_suppressed_issues(Path("f.py"), [], ["x = 1"]) == []

    def test_unsuppressed_issues_pass_through(self, tmp_path) -> None:
        issues = [_issue("rule-a", 1)]
        assert _filter_suppressed_issues(Path("f.py"), issues, ["x = 1"]) == issues

    def test_bare_noqa_removes_issue(self, tmp_path) -> None:
        issues = [_issue("rule-a", 1)]
        assert _filter_suppressed_issues(Path("f.py"), issues, ["bad()  # noqa"]) == []

    def test_scoped_noqa_keeps_other_rules(self, tmp_path) -> None:
        issues = [_issue("rule-a", 1), _issue("rule-b", 1)]
        kept = _filter_suppressed_issues(Path("f.py"), issues, ["bad()  # noqa: rule-a"])
        assert [i.rule_id for i in kept] == ["rule-b"]

    def test_file_level_exemption_applies(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / ".jcode"
        cfg.mkdir()
        (cfg / "ignored-rules.toml").write_text(
            '[[ignored_files]]\nfile = "vendor/"\nrules = ["rule-a"]\n', encoding="utf-8"
        )
        issues = [_issue("rule-a", 1), _issue("rule-b", 1)]
        kept = _filter_suppressed_issues(Path("vendor/x.py"), issues, ["bad()"])
        assert [i.rule_id for i in kept] == ["rule-b"]

    def test_original_list_not_mutated(self, tmp_path) -> None:
        """过滤必须返回新列表, 不得就地修改调用方传入的 issues。"""
        issues = [_issue("rule-a", 1)]
        _filter_suppressed_issues(Path("f.py"), issues, ["bad()  # noqa"])
        assert len(issues) == 1
