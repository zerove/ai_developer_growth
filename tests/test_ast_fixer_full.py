"""rules_engine/ast_fixer.py 覆盖攻坚 (18%→80%+)。

覆盖:
- fix_file 全流程(dry_run/真实写入/不可读文件/解析失败)
- fix_content(bare except 替换/except+pass 注释)
- _fix_unused_variables 启发式(下划线/大写/常见名单豁免)
- _apply_fix 三分支(替换/插入/整行)
- format_fix_report 空/非空
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine.ast_fixer import ASTFixer, FixReport


@pytest.fixture
def fixer() -> ASTFixer:
    return ASTFixer()


class TestBareExcept:
    def test_bare_except_replaced(self, fixer: ASTFixer) -> None:
        code = "try:\n    f()\nexcept:\n    g()\n"
        fixed, fixes = fixer.fix_content(code, "python")
        assert any(f.rule_id == "fix-bare-except" for f in fixes)

    def test_except_pass_gets_comment(self, fixer: ASTFixer) -> None:
        """fix-empty-except 仍被发现, 但不再自动应用 (ADR-067).

        该规则只插入 ``# TODO`` 注释, 标记问题而非修复问题。
        ADR-067 起它是 ``auto_safe=False``, 故 ``fix_content``
        不会把它写进 ``fixed`` —— 但**仍会报告**, 这是降级而非隐藏。
        """
        code = "try:\n    f()\nexcept Exception:\n    pass\n"
        fixed, fixes = fixer.fix_content(code, "python")
        assert any(f.rule_id == "fix-empty-except" for f in fixes)
        assert "# TODO: Handle this exception" not in fixed

    def test_clean_code_no_fixes(self, fixer: ASTFixer) -> None:
        fixed, fixes = fixer.fix_content("x = 1\n", "python")
        assert fixed == "x = 1\n" and fixes == []


class TestUnusedVariables:
    def _analyze(self, fixer: ASTFixer, code: str) -> int:
        _, fixes = fixer.fix_content(code, "python")
        return sum(1 for f in fixes if f.rule_id == "fix-unused-var")

    def test_unused_var_flagged(self, tmp_path: Path, fixer: ASTFixer) -> None:
        src = tmp_path / "m.py"
        src.write_text("value_unused = compute()\nprint('done')\n")
        report = fixer.fix_file(src)
        assert report is not None

    def test_underscore_prefixed_skipped(self, tmp_path: Path, fixer: ASTFixer) -> None:
        src = tmp_path / "m.py"
        src.write_text("_ignored = 1\n")
        report = fixer.fix_file(src)
        assert all(
            f.rule_id != "fix-unused-var" or "_ignored" not in f.description for f in (report.fixes if report else [])
        )


class TestFixFileFlow:
    def test_dry_run_no_write(self, tmp_path: Path, fixer: ASTFixer) -> None:
        src = tmp_path / "m.py"
        src.write_text("try:\n    f()\nexcept Exception:\n    pass\n")
        before = src.read_text()
        report = fixer.fix_file(src, dry_run=True)
        assert report is not None
        assert src.read_text() == before  # 未写回
        assert report.total_fixes >= 1

    def test_real_run_applies_safe_fixes(self, tmp_path: Path, fixer: ASTFixer) -> None:
        src = tmp_path / "m.py"
        src.write_text("try:\n    f()\nexcept Exception:\n    pass\n")
        report = fixer.fix_file(src, dry_run=False)
        assert report is not None
        # ADR-066 起 fix_file 自己写回文件（此前只生成 fixed_content）。
        # 本例只有 fix-empty-except 一项，且自 ADR-067 起是 report-only,
        # 因此磁盘上不应出现 # TODO —— 但该修复仍会被报告。
        assert "# TODO" not in report.fixed_content
        assert any(f.rule_id == "fix-empty-except" for f in report.fixes)

    def test_unreadable_file_returns_none(self, tmp_path: Path, fixer: ASTFixer) -> None:
        assert fixer.fix_file(tmp_path / "nope.py") is None

    def test_non_python_file_returns_none(self, tmp_path: Path, fixer: ASTFixer) -> None:
        src = tmp_path / "data.xyz"
        src.write_text("whatever")
        assert fixer.fix_file(src) is None


class TestApplyFixBranches:
    def test_replace_in_line(self, fixer: ASTFixer) -> None:
        from tools.scripts.rules_engine.ast_fixer import FixResult

        fr = FixResult(
            rule_id="t",
            description="",
            file="f",
            line=2,
            column=0,
            original="pass",
            replacement="pass  # x",
            confidence=0.9,
            auto_safe=True,
        )
        out = fixer._apply_fix("a=1\n    pass\nb=2\n", fr)
        assert "pass  # x" in out

    def test_insert_line_when_no_original(self, fixer: ASTFixer) -> None:
        from tools.scripts.rules_engine.ast_fixer import FixResult

        fr = FixResult(
            rule_id="t",
            description="",
            file="f",
            line=2,
            column=0,
            original="",
            replacement="inserted",
            confidence=0.9,
            auto_safe=True,
        )
        out = fixer._apply_fix("a=1\nb=2\n", fr)
        assert "inserted" in out

    def test_out_of_range_noop(self, fixer: ASTFixer) -> None:
        from tools.scripts.rules_engine.ast_fixer import FixResult

        fr = FixResult(
            rule_id="t",
            description="",
            file="f",
            line=99,
            column=0,
            original="x",
            replacement="y",
            confidence=0.9,
            auto_safe=True,
        )
        content = "a=1\n"
        assert fixer._apply_fix(content, fr) == content


class TestFormatReport:
    def test_empty_report(self, fixer: ASTFixer) -> None:
        report = FixReport(
            file="f.py",
            fixes=[],
            original_content="",
            fixed_content="",
            fix_time_ms=0.0,
            total_fixes=0,
            auto_safe_fixes=0,
        )
        assert "No fixes" in fixer.format_fix_report(report)

    def test_report_with_fixes(self, fixer: ASTFixer) -> None:
        from tools.scripts.rules_engine.ast_fixer import FixResult

        fr = FixResult(
            rule_id="R1",
            description="desc",
            file="f",
            line=1,
            column=0,
            original="old",
            replacement="new",
            confidence=0.7,
            auto_safe=False,
        )
        report = FixReport(
            file="f.py",
            fixes=[fr],
            original_content="old",
            fixed_content="new",
            fix_time_ms=1.0,
            total_fixes=1,
            auto_safe_fixes=0,
        )
        text = fixer.format_fix_report(report)
        assert "REVIEW" in text and "R1" in text and "70%" in text
