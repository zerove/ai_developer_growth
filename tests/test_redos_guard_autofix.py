# 拆分自 tests/test_redos_guard.py

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

import time
from pathlib import Path
from typing import Any

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


class TestAutoFixRuleIdIsGuarded:
    r"""`tools/scripts/auto_fix.py` 的 RegexFixProvider 把 issue.rule_id 当正则用。

    与同名的 `tools/scripts/rules_engine/auto_fix.py` 是**两个不同文件**: 后者
    pattern 全来自硬编码的 FIX_PATTERNS, 无需守卫。审计报告把两者混为一谈
    (行号 545 属于顶层这个), 导致该点被漏了两轮。

    此处三面皆不可信: rule_id(规则配置) 当 pattern、fix_replacement(规则配置)
    当 replacement、original_line(源码) 当被替换文本, 且结果**写回文件**。

    夹具设计的关键: 危险 pattern 必须**真的能匹配**夹具行。否则撤掉守卫后
    `re.sub` 不产生替换, `results` 仍为空, 用例会因错误的原因通过 —— 这正是
    本用例第一版的缺陷。
    """

    # 能匹配夹具行(全是 x), 故"若无守卫则必定产生 FixAction"可被断言
    DANGER = r"(x|xx)+"
    # 正常 rule_id: 字面量, 无歧义
    NORMAL = "bare_except_marker"
    HOSTILE_LINE = "xxxxxx!" + "\n"

    @staticmethod
    def _issue(rule_id: str) -> Any:
        from tools.scripts.rules_engine.models import Issue

        return Issue(
            rule_id=rule_id,
            severity="error",
            category="c",
            file="a.py",
            line=1,
            column=1,
            message="m",
            fix_replacement="y",
        )

    @staticmethod
    def _provider(tmp_path: Path) -> Any:
        from tools.scripts import auto_fix as af

        target = tmp_path / "a.py"
        # 两个 pattern 都必须落在**第 1 行**: generate_fixes 只处理 issue.line 指向的那一行
        target.write_text("xxxxxx! bare_except_marker = 1\n", encoding="utf-8")
        return af.RegexFixProvider("regex"), target

    def test_dangerous_rule_id_is_skipped(self, tmp_path: Path) -> None:
        provider, target = self._provider(tmp_path)

        results = provider.generate_fixes(self._issue(self.DANGER), str(target))

        assert results == [], "危险 rule_id 必须被跳过, 不得产生 FixAction"
        assert target.read_text(encoding="utf-8") == "xxxxxx! bare_except_marker = 1\n", "文件不得被改写"

    def test_normal_rule_id_still_applies(self, tmp_path: Path) -> None:
        """反向约束: 正常 rule_id 仍须执行替换, 守卫不得误伤真实规则。"""
        provider, target = self._provider(tmp_path)

        results = provider.generate_fixes(self._issue(self.NORMAL), str(target))

        assert results, "正常 rule_id 未产生 FixAction —— 守卫误伤了真实规则"

    def test_guard_is_consulted_with_rule_id(self, tmp_path: Path, monkeypatch: Any) -> None:
        """断言守卫确实被询问, 而非恰好未走到该分支。"""
        from tools.scripts import auto_fix as af

        provider, target = self._provider(tmp_path)
        seen: list[str] = []
        real = af.guard_pattern
        monkeypatch.setattr(af, "guard_pattern", lambda p, ctx="": seen.append(p) or real(p, ctx))

        provider.generate_fixes(self._issue(self.NORMAL), str(target))

        assert self.NORMAL in seen, "守卫未被询问"

    def test_catastrophic_rule_id_does_not_hang(self, tmp_path: Path) -> None:
        """长 x 串 + 不匹配尾字符: 若守卫失效会指数回溯。此处只断言"及时返回"。"""
        provider, target = self._provider(tmp_path)
        target.write_text("x" * 40 + "!\n", encoding="utf-8")

        start = time.perf_counter()
        provider.generate_fixes(self._issue(r"(x|xx)+$"), str(target))
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"疑似灾难性回溯, 耗时 {elapsed:.2f}s"


class TestRuleLoaderIngestGate:
    r"""载入点闸门: `_drop_dangerous_patterns` 覆盖 load_rules 与 load_custom_rules。

    这是**深度修复** —— 全仓 60+ 处 pattern 取自规则配置, 逐点接线必然漏(审计曾因
    两个同名文件混淆而漏掉 tools/scripts/auto_fix.py, 连续两轮未被发现)。在载入点
    拦一次, 下游调用点自动免疫。

    之所以能默认开启: 已发行规则逐条静态分析命中 0 条, 即对现有行为是可证明的 no-op。
    """

    DANGER = r"(x|xx)+$"
    NORMAL = r"bare_except"

    @staticmethod
    def _rules_yml(tmp_path: Path, patterns: dict[str, str]) -> None:
        adg = tmp_path / ".adg"
        adg.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"  - id: {rid}\n    pattern: '{pat}'\n    message: m" for rid, pat in patterns.items())
        (adg / "rules.yml").write_text(f"anti_patterns:\n{body}\n", encoding="utf-8")

    def test_dangerous_custom_rule_is_dropped(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.rule_loader import load_custom_rules

        self._rules_yml(tmp_path, {"evil": self.DANGER, "good": self.NORMAL})
        rules = load_custom_rules(tmp_path)
        ids = {r.get("id") for r in rules.get("anti_patterns", [])}

        assert "evil" not in ids, "危险规则未被丢弃"
        assert "good" in ids, "正常规则被误删"

    def test_dangerous_rule_is_actually_removed_not_flagged(self, tmp_path: Path) -> None:
        """只打标记等于没删: 下游仍会 re.search(item['pattern']) 执行它。"""
        from tools.scripts.rules_engine.rule_loader import load_custom_rules

        self._rules_yml(tmp_path, {"evil": self.DANGER})
        rules = load_custom_rules(tmp_path)
        item = next(iter(rules.get("anti_patterns", [])), None)

        assert item is None, "危险规则仍在列表中 —— 闸门形同虚设"

    def test_dangerous_naming_pattern_is_dropped(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _drop_dangerous_patterns

        rules = {
            "naming": {
                "file": {
                    "evil": {"pattern": self.DANGER},
                    "good": {"pattern": r"^[a-z][a-z0-9_]*\.rs$"},
                }
            }
        }
        out = _drop_dangerous_patterns(rules)
        kinds = out["naming"]["file"]

        assert "evil" not in kinds, "危险 naming pattern 未被丢弃"
        assert "good" in kinds, "正常 naming pattern 被误删"

    def test_loader_never_raises_on_malformed_rules(self, tmp_path: Path) -> None:
        """配置坏了应丢规则, 而不是让检查器整体崩掉。"""
        from tools.scripts.rules_engine.rule_loader import _drop_dangerous_patterns

        weird = {
            "anti_patterns": [
                None,
                "not-a-dict",
                {"id": "x", "pattern": 123},
                {"id": "y", "pattern": ""},
                {"id": "z"},
            ],
            "naming": {"python": "not-a-dict"},
        }
        assert _drop_dangerous_patterns(weird) is weird

    def test_invalid_rule_ids_are_dropped(self) -> None:
        """无效规则 ID（缺失/空/空白/含空白）应在载入净化阶段丢弃。"""
        from tools.scripts.rules_engine.rule_loader import _drop_dangerous_patterns

        rules = {
            "anti_patterns": [
                {"id": "", "pattern": "TODO", "message": "x"},
                {"id": "   ", "pattern": "TODO", "message": "x"},
                {"id": "bad id", "pattern": "TODO", "message": "x"},
                {"pattern": "TODO", "message": "x"},
                {"id": "ok-id", "pattern": "TODO", "message": "x"},
            ]
        }
        out = _drop_dangerous_patterns(rules)
        ids = [r.get("id") for r in out["anti_patterns"] if isinstance(r, dict)]
        assert ids == ["ok-id"]

    def test_invalid_regex_patterns_are_dropped(self) -> None:
        """不可编译的正则应被丢弃（pattern）或剥离（exclude_pattern/naming）。"""
        from tools.scripts.rules_engine.rule_loader import _drop_dangerous_patterns

        rules = {
            "anti_patterns": [
                {"id": "bad-pattern", "pattern": "(", "message": "x"},
                {"id": "bad-exclude", "pattern": "TODO", "exclude_pattern": "[", "message": "x"},
                {"id": "ok-rule", "pattern": "TODO", "message": "x"},
            ],
            "naming": {
                "python": {
                    "bad": {"pattern": "("},
                    "good": {"pattern": r"^[a-z_]+$"},
                }
            },
        }
        out = _drop_dangerous_patterns(rules)
        ids = [r.get("id") for r in out["anti_patterns"] if isinstance(r, dict)]
        assert ids == ["bad-exclude", "ok-rule"]
        bad_exclude = next(r for r in out["anti_patterns"] if r.get("id") == "bad-exclude")
        assert "exclude_pattern" not in bad_exclude
        assert "bad" not in out["naming"]["python"]
        assert "good" in out["naming"]["python"]

    def test_strict_custom_rule_ids_are_optional_in_shared_loader(self, monkeypatch: Any) -> None:
        """共享规则净化路径在 env 严格模式下可选过滤不合规 ID。"""
        from tools.scripts.rules_engine.rule_loader import _drop_dangerous_patterns

        rules = {
            "anti_patterns": [
                {"id": "sec-001", "pattern": "TODO", "message": "x"},
                {"id": "My.Bad", "pattern": "TODO", "message": "x"},
            ]
        }
        monkeypatch.delenv("ADG_STRICT_CUSTOM_RULE_IDS", raising=False)
        out = _drop_dangerous_patterns(rules)
        assert [r.get("id") for r in out["anti_patterns"]] == ["sec-001", "My.Bad"]

        rules2 = {
            "anti_patterns": [
                {"id": "sec-001", "pattern": "TODO", "message": "x"},
                {"id": "My.Bad", "pattern": "TODO", "message": "x"},
            ]
        }
        monkeypatch.setenv("ADG_STRICT_CUSTOM_RULE_IDS", "1")
        out2 = _drop_dangerous_patterns(rules2)
        assert [r.get("id") for r in out2["anti_patterns"]] == ["sec-001"]
