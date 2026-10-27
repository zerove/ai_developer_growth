"""ReDoS 守卫回归测试：静态分析必须识破"量词包住重叠分支"。

## 要锁住的缺陷

旧守卫用字符串正则判断危险结构，其中 `_DANGEROUS_PATTERNS[0]` 要求
**组内含量词**::

    re.compile(r"\\([^)]*[+*][^)]*\\)[+*]")

于是只有 `(a+)+` 这类嵌套量词会被拦下，而**重复分支**与**前缀重叠分支**
全部漏网::

    (a|aa)+$   (x|x)+$   (x|xx)+$   (a|a)*$   (?:x|x)+$

实测（修复前，n=3000 的对抗输入，各自独立进程 6 秒上限）::

    (a+)+$      HANG >6.0s      守卫 True
    (a|aa)+$    HANG >6.0s      守卫 False   <-- 漏网
    (x|x)+$     HANG >6.0s      守卫 False   <-- 漏网
    (x|xx)+$    HANG >6.0s      守卫 False   <-- 漏网

7 个真实挂死模式里守卫只抓到 2 个。

## 修法

改用 `re._parser` 静态分析，把正则拆成语法树后判定两类结构：

1. **嵌套歧义量词** —— 无界量词内再套无界量词；
2. **量词下的重叠分支** —— 无界量词包住 BRANCH 且备选不互斥。

## 反向约束：不得把安全惯用法误判

误判的代价是**一条真实规则被静默丢弃**（与 fail-open 同族）。
`^\\w+\\.(\\w+\\.)*\\w+$` 这类"内层 `*` 后紧跟强制分隔符"的分界唯一惯用法
必须判为安全 —— 旧启发式正是在这里误报（实测 467 条真实规则中唯一确凿的误报）。
"""

import re
from pathlib import Path
from typing import Any

import pytest

from tools.scripts.adg_cli import check as adg_check
from tools.scripts.rules_engine import regex_cache
from tools.scripts.rules_engine.regex_cache import (
    _is_dangerous,
    get_dangerous,
    guard_pattern,
    is_dangerous,
    scan_dangerous_patterns,
)

EXPLOITABLE = [
    r"(a+)+$",  # 嵌套量词 —— 旧守卫已能拦
    r"([a-z]+)*$",
    r"(\w+\s?)*$",
    r"(a*)*$",
    r"(a|aa)+$",  # 前缀重叠分支 —— 旧守卫漏网
    r"(a|a)*$",  # 重复分支 —— 旧守卫漏网
    r"(x|x)+$",
    r"(x|xx)+$",
    r"(?:x|x)+$",
]


BENIGN = [
    r"\b\w+\b",
    r"except\s*:",
    r"^\s*|\s*$",
    r"(?:password|secret)\s*=\s*[\"'][^\"']+[\"']",
    r"^[a-z][a-z0-9_]*\.py$",
    r"\beval\s*\(|\bexec\s*\(",
    # 内层 * 后紧跟强制分隔符 -> 分界唯一, 必须安全
    r"^[a-z][a-z0-9]*\.([a-z][a-z0-9]*\.)*[a-z][a-z0-9]*$",
]


class TestExploitablePatternsAreCaught:
    @pytest.mark.parametrize("pattern", EXPLOITABLE)
    def test_caught(self, pattern: str) -> None:
        assert get_dangerous(pattern) is True, f"{pattern!r} 会挂死检查进程却未被拦下"

    def test_old_heuristic_alone_missed_these(self) -> None:
        """记录守卫能力提升: 旧的那条"组内含量词"正则对分支类结构完全无效。"""
        legacy = [re.compile(r"\([^)]*[+*][^)]*\)[+*]")]
        bypass = [r"(a|aa)+$", r"(x|x)+$", r"(x|xx)+$"]
        assert not any(pat.search(p) for p in bypass for pat in legacy)
        assert all(get_dangerous(p) for p in bypass)


class TestBenignPatternsAreNotFlagged:
    @pytest.mark.parametrize("pattern", BENIGN)
    def test_not_flagged(self, pattern: str) -> None:
        """误判 = 一条真实规则被静默丢弃, 与 fail-open 同族。"""
        assert _is_dangerous(pattern) is False, f"{pattern!r} 被误判为危险"

    def test_top_level_alternation_is_safe(self) -> None:
        """BRANCH 不在无界量词内 -> 无回溯放大 (旧实现与新实现都应放行)。"""
        assert _is_dangerous(r"(?:password|secret)") is False
        assert _is_dangerous(r"(cat|dog)") is False


class TestPublicApiStability:
    def test_is_dangerous_matches_get_dangerous(self) -> None:
        for p in EXPLOITABLE + BENIGN:
            assert is_dangerous(p) == get_dangerous(p)

    def test_scan_dangerous_patterns_shape(self) -> None:
        out = scan_dangerous_patterns([r"(a|aa)+$", r"\b\w+\b"])
        assert out == [(r"(a|aa)+$", True), (r"\b\w+\b", False)]

    def test_invalid_pattern_does_not_raise(self) -> None:
        """非法正则不得把守卫本身变成抛异常源。"""
        assert _is_dangerous("(unclosed") is False

    def test_cache_api_intact(self) -> None:
        assert regex_cache.get_compiled(r"\d+").search("a1") is not None
        regex_cache.clear_cache()
        assert regex_cache.cache_stats()["cached_patterns"] == 0


class TestGuardPatternIsVisible:
    """跳过必须留痕 —— 静默丢弃规则无法与"检查通过"区分。"""

    @pytest.fixture
    def logged(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        """替换 loguru logger —— 它写 stderr, caplog 捕获不到。"""
        seen: list[str] = []
        monkeypatch.setattr(regex_cache, "logger", type("L", (), {"warning": staticmethod(lambda m: seen.append(m))})())
        regex_cache._WARNED_PATTERNS.clear()
        return seen

    def test_logs_once_per_pattern(self, logged: list[str]) -> None:
        """热路径每文件每规则都会调用, 不去重会刷出上千行。"""
        for _ in range(5):
            assert guard_pattern(r"(a|aa)+$", "unit") is True
        assert len(logged) == 1
        assert "灾难性回溯" in logged[0]
        assert "(a|aa)+$" in logged[0], "日志必须含具体 pattern, 否则无法定位是哪条规则被丢"
        assert "[unit]" in logged[0], "日志必须含调用点上下文"

    def test_no_log_for_safe_pattern(self, logged: list[str]) -> None:
        assert guard_pattern(r"\b\w+\b") is False
        assert logged == []

    def test_message_has_no_unsubstituted_placeholders(self, logged: list[str]) -> None:
        """loguru 用 {} 而非 %s 格式化 —— 用错会让占位符原样打进日志。"""
        guard_pattern(r"(a|aa)+$", "ctx")
        assert "%s" not in logged[0] and "{}" not in logged[0]


class TestWiringCoversUnguardedSites:
    """守卫必须真正接在编译/匹配之前, 而不只是存在于 regex_cache 里。

    ## 为何用"间谍"而非"跑给它看"

    最早这组用例直接拿 3000 字符的对抗输入调真实匹配, 断言不挂死。结果: 撤掉
    守卫的变异不是让用例**失败**, 而是让整个测试进程**挂死** —— 无法与真实
    卡死区分, 变异测试也就失去意义。

    改为替换模块内 `guard_pattern` 引用为间谍, 断言"该点在危险 pattern 上确实
    询问过守卫且被判定为危险"。这样:
      - 变异立即失败而非挂死;
      - 输入可以是良性的, 用例恒在毫秒级完成;
      - 断言语义从"跑得快"变成"守卫在路径上", 才是真正要锁的东西。
    """

    @staticmethod
    def _spy(monkeypatch: pytest.MonkeyPatch, module: Any) -> list[tuple[str, str, bool]]:
        calls: list[tuple[str, str, bool]] = []
        real = module.guard_pattern

        def recording(pattern: str, context: str = "") -> bool:
            dangerous = real(pattern, context)
            calls.append((pattern, context, dangerous))
            return dangerous

        monkeypatch.setattr(module, "guard_pattern", recording)
        return calls

    DANGER = r"(x|xx)+$"

    def test_engine_exclude_patterns_guarded(self, tmp_path: Any, monkeypatch: Any) -> None:

        from tools.scripts.rules_engine import anti_pattern_checker as eng

        calls = self._spy(monkeypatch, eng)
        assert (
            eng._is_pattern_excluded(Path(tmp_path) / "a.py", "harmless\n", {"exclude_patterns": [self.DANGER]})
            is False
        )
        assert any(c[2] for c in calls), "exclude_patterns 未接入守卫"
        assert self.DANGER in [c[0] for c in calls]

    def test_adg_cli_exclude_patterns_guarded(self, tmp_path: Any, monkeypatch: Any) -> None:

        calls = self._spy(monkeypatch, adg_check)
        assert (
            adg_check._is_pattern_excluded(Path(tmp_path) / "a.py", "harmless\n", {"exclude_patterns": [self.DANGER]})
            is False
        )
        assert any(c[2] for c in calls), "adg_cli 的 exclude_patterns 未接入守卫"

    def test_adg_cli_main_multiline_guarded(self, tmp_path: Any, monkeypatch: Any) -> None:

        calls = self._spy(monkeypatch, adg_check)
        issues: list[Any] = []
        pattern_def = {"id": "evil", "severity": "error", "pattern": self.DANGER}
        adg_check._scan_multiline(Path(tmp_path) / "a.py", "harmless\n", self.DANGER, 0, pattern_def, issues)
        assert issues == []
        assert any(c[2] for c in calls), "主 pattern (multiline) 未接入守卫"

    def test_adg_cli_main_line_guarded(self, tmp_path: Any, monkeypatch: Any) -> None:

        calls = self._spy(monkeypatch, adg_check)
        issues: list[Any] = []
        pattern_def = {"id": "evil", "severity": "error", "pattern": self.DANGER}
        adg_check._scan_line_by_line(Path(tmp_path) / "a.py", ["harmless"], self.DANGER, 0, pattern_def, issues)
        assert issues == []
        assert any(c[2] for c in calls), "主 pattern (逐行) 未接入守卫"

    def test_adg_cli_exclude_lines_guarded(self, tmp_path: Any, monkeypatch: Any) -> None:

        calls = self._spy(monkeypatch, adg_check)
        issues: list[Any] = []
        pattern_def = {"id": "p", "severity": "error", "exclude_lines": [self.DANGER]}
        adg_check._scan_line_by_line(Path(tmp_path) / "a.py", ["harmless"], r"zzz", 0, pattern_def, issues)
        assert any(c[2] for c in calls), "exclude_lines 未接入守卫"

    def test_engine_exclude_lines_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts.rules_engine import anti_pattern_checker as eng

        calls = self._spy(monkeypatch, eng)
        pattern_def = {"id": "p", "severity": "error", "exclude_lines": [self.DANGER]}
        assert eng._check_line_patterns([(1, "harmless")], r"zzz", 0, pattern_def, "a.py") == []
        assert any(c[2] for c in calls), "anti_pattern_checker 的 exclude_lines 未接入守卫"

    def test_engine_main_pattern_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts.rules_engine import anti_pattern_checker as eng

        calls = self._spy(monkeypatch, eng)
        pattern_def = {"id": "evil", "severity": "error", "pattern": self.DANGER}
        assert eng._check_line_patterns([(1, "harmless")], self.DANGER, 0, pattern_def, "a.py") == []
        assert any(c[2] for c in calls), "anti_pattern_checker 主 pattern 未接入守卫"

    def test_validators_pipeline_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts.rules_engine.validators import pipeline

        calls = self._spy(monkeypatch, pipeline)
        assert pipeline._check_pattern_against_lines(["harmless"], {"pattern": self.DANGER}, "a.py") == []
        assert any(c[2] for c in calls), "validators/pipeline 未接入留痕版守卫"
