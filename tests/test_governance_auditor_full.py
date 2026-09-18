#!/usr/bin/env python3
"""Tests for governance-auditor.py full() 并行化 (P2-3)。

覆盖: 八项检查语义、失败按检查计数、确定性失败顺序、
无按语言拆分重叠、语言字符串正确转发。
"""

from __future__ import annotations

import importlib.util
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"

# full() 中检查的定义顺序（确定性报告依据）
CHECK_ORDER = [
    "Lint",
    "Format",
    "Type Check",
    "Test",
    "Security",
    "Governance Docs",
    "AI-SDLC Compliance",
    "AI Quality Gate",
]


def _load_auditor() -> Any:
    """动态加载 .jcode/scripts/governance-auditor.py（非包路径，需 importlib）。"""
    target = _SCRIPTS_DIR / "governance-auditor.py"
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("jcode_governance_auditor", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def auditor() -> Any:
    return _load_auditor()


def _install_fakes(ga: Any, results: dict[str, bool] | None = None) -> tuple[list[tuple[str, object]], list[str]]:
    """替换 full() 依赖的检查函数，记录调用参数。

    results: {检查名: bool}，缺省为 True。
    返回 (lang_calls, independent_calls)。
    """
    results = results or {}
    lang_calls: list[tuple[str, object]] = []
    independent_calls: list[str] = []

    def make_lang(name: str) -> Callable[[object], bool]:
        def fake(lang: object) -> bool:
            lang_calls.append((name, lang))
            return results.get(name, True)

        return fake

    ga.lint = make_lang("Lint")
    ga.format_check = make_lang("Format")
    ga.typecheck = make_lang("Type Check")
    ga.test = make_lang("Test")
    ga.security = make_lang("Security")

    def make_independent(name: str) -> Callable[[], bool]:
        def fake() -> bool:
            independent_calls.append(name)
            return results.get(name, True)

        return fake

    ga.validate_governance_docs = make_independent("Governance Docs")
    ga.check_ai_sdlc_compliance = make_independent("AI-SDLC Compliance")
    ga.ai_quality_gate = make_independent("AI Quality Gate")
    return lang_calls, independent_calls


def _quiet(ga: Any, captured: list[str] | None = None) -> None:
    """静默输出；captured 非空时收集 print 内容。"""
    ga.print_section = lambda *a, **k: None
    if captured is not None:
        ga.print = lambda *a, **k: captured.append(" ".join(str(x) for x in a))
    else:
        ga.print = lambda *a, **k: None


def test_full_success_all_checks_pass(auditor: Any) -> None:
    """全部 8 项检查通过时返回 0，且每项恰好执行一次。"""
    lang_calls, independent_calls = _install_fakes(auditor)
    _quiet(auditor)
    rc = auditor.full("python,typescript")
    assert rc == 0
    assert sorted(name for name, _ in lang_calls) == ["Format", "Lint", "Security", "Test", "Type Check"]
    assert sorted(independent_calls) == ["AI Quality Gate", "AI-SDLC Compliance", "Governance Docs"]


def test_full_no_per_language_overlap_and_forwards_lang_string(auditor: Any) -> None:
    """语言检查不按语言拆分：5 项语言检查各收到完整语言字符串。"""
    lang_calls, independent_calls = _install_fakes(auditor)
    _quiet(auditor)
    rc = auditor.full("python,typescript")
    assert rc == 0
    # 每项语言检查恰好调用一次（2 语言不产生 10 项任务）
    assert len(lang_calls) == 5
    for name, lang_arg in lang_calls:
        assert lang_arg == "python,typescript", f"{name} 收到 {lang_arg!r}"
    # 独立检查 3 项，总计 8 项
    assert len(independent_calls) == 3


def test_full_failure_count_per_check(auditor: Any) -> None:
    """失败按检查计数：一项语言检查失败计 1，而非按语言计 2。"""
    lang_calls, independent_calls = _install_fakes(auditor, results={"Lint": False})
    _quiet(auditor)
    rc = auditor.full("python,typescript")
    assert rc == 1
    assert len(lang_calls) == 5
    assert len(independent_calls) == 3


def test_full_exception_reported(auditor: Any) -> None:
    """检查抛异常时计入失败并标注异常信息。"""
    lang_calls, independent_calls = _install_fakes(auditor)

    def boom() -> bool:
        raise RuntimeError("boom")

    auditor.validate_governance_docs = boom
    captured: list[str] = []
    _quiet(auditor, captured)
    rc = auditor.full("python")
    assert rc == 1
    assert any("Governance Docs (异常: boom)" in line for line in captured)


def test_full_deterministic_failure_order(auditor: Any) -> None:
    """失败列表按检查定义顺序输出，与完成顺序无关。"""

    # 第一项检查最慢完成，其余快速失败：若按完成顺序收集，Lint 会排最后
    def slow_lint(lang: object) -> bool:
        time.sleep(0.3)
        return False

    def fast_fail(lang: object) -> bool:
        return False

    auditor.lint = slow_lint
    auditor.format_check = fast_fail
    auditor.typecheck = fast_fail
    auditor.test = fast_fail
    auditor.security = fast_fail
    auditor.validate_governance_docs = lambda: False
    auditor.check_ai_sdlc_compliance = lambda: False
    auditor.ai_quality_gate = lambda: False
    captured: list[str] = []
    _quiet(auditor, captured)
    rc = auditor.full("python")
    assert rc == 8
    fail_line = next(line for line in captured if line.startswith("❌ 失败:"))
    assert fail_line == "❌ 失败: " + ", ".join(CHECK_ORDER)
