"""门禁 fail-open 契约测试：skipped 携带 error 时不得豁免 (ADR-052 收窄)。

## 要锁住的缺陷

`_prepare_file_check` 曾把非 UTF-8 文件的 `UnicodeDecodeError` 吞掉并返回
`(lang, rules, None, None)`，`check_file` 据此产出 `skipped=True` + **零 issue**。
而报告层的通过判定**无条件豁免 skipped**（ADR-052, Phase 33b-12）::

    non_skipped = [r for r in results if not r.skipped]
    passed = all(r.passed for r in non_skipped) if non_skipped else True

于是「该文件根本没被检查」与「该文件检查通过」在门禁眼里完全等价 —— 一个
**实际未被检查**的文件让门禁返回 passed。

同一形态的缺陷当时已在 `_file_not_found_result` 上线：它产出
`skipped=True` + `error` 级 Issue，但因被豁免，**门禁照样 passed**。

## 实测（修复前）

```
summary([non-utf8])   : {'total_errors': 0, 'passed': True}
summary([not-found])  : {'total_errors': 1, 'passed': True}   <-- 已有 error 却 passed
stats([clean, nf])    : (1, 0, 2, 0)                          <-- failures=0
```

## 契约要点

1. skipped 仅在**零 error** 时可豁免 —— 「无需检查」与「检查失败」必须可区分；
2. 非 UTF-8 文件必须留下 `error` 级 Issue（`file-decode-error`），
   严重度不得降级为 warning，否则退出码仍可能为 0；
3. **不得制造误报**：零 error 的 skip（空文件、未知语言）仍必须豁免。

## 夹具隔离（ADR-078 的 M2 教训）

「当夹具中存在其他能独立触发同一信号的因素时，等价性断言会失去辨别力」。
故每个用例只放**一个**被测因素：豁免类用例用全部干净的文件，
失败类用例用**只有**目标文件一个结果的列表，不混入任何其他 error 来源。
"""

from pathlib import Path

import pytest

from tools.scripts.report_generator import (
    _build_json_summary,
    _count_summary_stats,
)
from tools.scripts.rules_engine.checker import check_file


@pytest.fixture
def undecodable(tmp_path: Path) -> Path:
    """一个 .py 文件 —— 引擎认识这个语言，但内容不是 UTF-8。"""
    fp = tmp_path / "bad.py"
    fp.write_bytes(b"x = 1\n\xff\xfe\x00\n")
    return fp


@pytest.fixture
def empty(tmp_path: Path) -> Path:
    """零字节文件 —— 真的无需检查（skip 的正当形态）。"""
    fp = tmp_path / "empty.py"
    fp.write_bytes(b"")
    return fp


@pytest.fixture
def unknown_lang(tmp_path: Path) -> Path:
    """引擎不认识的扩展名 —— 真的无需检查。"""
    fp = tmp_path / "notes.txt"
    fp.write_text("just some prose\n", encoding="utf-8")
    return fp


class TestUndecodableFileIsVisible:
    """非 UTF-8：被支持语言却读不出来，属「检查失败」而非「无需检查」。"""

    def test_records_error_issue(self, undecodable: Path) -> None:
        result = check_file(undecodable, None)

        assert result.skipped is True
        assert [i.rule_id for i in result.issues] == ["file-decode-error"]

    def test_issue_is_error_not_warning(self, undecodable: Path) -> None:
        """降级为 warning 会让修复形同虚设 —— 退出码依据 error 判定。"""
        result = check_file(undecodable, None)

        assert result.error_count == 1, "必须以 error 级留痕"
        assert result.issues[0].severity == "error"

    def test_fails_gate(self, undecodable: Path) -> None:
        """用户可见的判据：报告里的 passed。"""
        summary = _build_json_summary([check_file(undecodable, None)])

        assert summary["total_errors"] == 1
        assert summary["passed"] is False, "未检查的文件被呈现为检查通过 —— fail-open"

    def test_counts_as_junit_failure(self, undecodable: Path) -> None:
        _errors, _warnings, tests, failures = _count_summary_stats([check_file(undecodable, None)])

        assert (tests, failures) == (1, 1)

    def test_does_not_mask_a_clean_sibling(self, undecodable: Path, tmp_path: Path) -> None:
        """混入一个干净文件后仍必须失败（clean 文件不产生独立 error）。"""
        clean = tmp_path / "clean.py"
        clean.write_text("x = 1\n", encoding="utf-8")

        summary = _build_json_summary([check_file(clean, None), check_file(undecodable, None)])

        assert summary["total_errors"] == 1
        assert summary["passed"] is False


class TestFileNotFoundIsVisible:
    """同一形态的缺陷当时已随 _file_not_found_result 上线。"""

    def test_missing_file_fails_gate(self, tmp_path: Path) -> None:
        summary = _build_json_summary([check_file(tmp_path / "ghost.py", None)])

        assert summary["total_errors"] == 1
        assert summary["passed"] is False, "文件不存在却被呈现为通过"

    def test_missing_file_counts_as_failure(self, tmp_path: Path) -> None:
        _errors, _warnings, tests, failures = _count_summary_stats([check_file(tmp_path / "ghost.py", None)])

        assert (tests, failures) == (1, 1)


class TestNoFalsePositive:
    """收窄豁免不得反过来把正当的 skip 变成失败。"""

    def test_empty_file_still_exempt(self, empty: Path) -> None:
        summary = _build_json_summary([check_file(empty, None)])

        assert summary["total_errors"] == 0
        assert summary["passed"] is True, "空文件无需检查, 不得误报"

    def test_unknown_language_still_exempt(self, unknown_lang: Path) -> None:
        summary = _build_json_summary([check_file(unknown_lang, None)])

        assert summary["total_errors"] == 0
        assert summary["passed"] is True, "未知语言无需检查, 不得误报"

    def test_all_exempt_skips_pass(self, empty: Path, unknown_lang: Path) -> None:
        """全部为正当 skip 时 passed 仍为 True（不得引入「全是 skip 就红」）。"""
        results = [check_file(empty, None), check_file(unknown_lang, None)]

        assert _build_json_summary(results)["passed"] is True
        assert _count_summary_stats(results)[3] == 0

    def test_empty_result_list_passes(self) -> None:
        assert _build_json_summary([])["passed"] is True

    def test_clean_file_still_passes(self, tmp_path: Path) -> None:
        clean = tmp_path / "ok.py"
        clean.write_text("def f() -> int:\n    return 1\n", encoding="utf-8")

        summary = _build_json_summary([check_file(clean, None, run_linters=False)])

        assert summary["passed"] is True
