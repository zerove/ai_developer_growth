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

from pathlib import Path
from typing import Any

import pytest

from tools.scripts.rules_engine.regex_cache import (
    _is_dangerous,
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


class TestNoSilentRegressionOnRealRules:
    """真实规则语料不得因守卫而被整片丢弃。"""

    def test_rule_corpus_dangerous_rate_is_small(self) -> None:
        """实测 467 条真实规则中 3 条被判危险 (0.6%), 均为保守方向。"""
        import pathlib

        import yaml

        root = pathlib.Path(__file__).resolve().parent.parent
        patterns: set[str] = set()
        for f in root.glob("ai-dev-framework/**/*.yml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
            except Exception:
                continue

            def walk(node: Any) -> None:
                if isinstance(node, dict):
                    for k, v in node.items():
                        if k in ("pattern", "exclude_pattern") and isinstance(v, str):
                            patterns.add(v)
                        else:
                            walk(v)
                elif isinstance(node, list):
                    for v in node:
                        walk(v)

            walk(data)

        assert len(patterns) > 100, "语料采样异常, 测试失去意义"
        flagged = [p for p in patterns if _is_dangerous(p)]
        rate = len(flagged) / len(patterns)
        assert rate < 0.02, f"误报率 {rate:.2%} 过高, 会静默丢弃过多真实规则: {flagged[:3]}"


class TestWiringCoversLspAndNaming:
    r"""lsp_server / naming_analyzer 的 pattern 同样来自规则配置, 必须接入守卫。

    与既有 6 点同属一类威胁: pattern 取自 anti_patterns / naming 规则, 在 PR
    场景由外部贡献者控制。此前只接了 adg_cli 与 anti_pattern_checker, 这两处
    漏掉 —— 接线时立刻暴露: 守卫误判 `@\w+(?:\.\w+)*\.ignore`, 静默禁用了整条
    命名检查 (34 个测试变红), 反证接线 + 跑测试缺一不可。
    """

    DANGER = r"(x|xx)+$"
    SAFE = r"\w+"
    # 刻意取**短**输入 (4 字符)。指数级回溯需要长度才爆发: 守卫在位时直接返回;
    # 守卫被撤掉时 2^4 的代价可忽略, 间谍随即记录到 0 次调用而干净失败。
    # 若换成长输入, 变异会让用例**挂死**而非失败 —— 无法与真实卡死区分。
    HOSTILE = "xxx!"

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

    def test_naming_file_rule_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts import naming_analyzer as na

        calls = self._spy(monkeypatch, na)
        assert na._check_filename("a.py", "python", {"file": {"pattern": self.DANGER}}) == []
        assert any(c[2] for c in calls), "naming/file 未接入守卫"

    def test_naming_safe_pattern_still_enforced(self, monkeypatch: Any) -> None:
        r"""反向约束: 安全 pattern 必须照常产出 issue (守卫不得误伤真实规则)。

        用 `^[a-z][a-z0-9_]*\.py$` —— 它在开头有 `^` 锚, re.match 才会因
        BadName 开头大写而判否。裸 `\w+` 不行: re.match 只锚定开头, `\w+`
        能匹配 BadName 的前缀, 本就不该报。
        """
        from tools.scripts import naming_analyzer as na

        rule = {"file": {"pattern": r"^[a-z][a-z0-9_]*\\.py$"}}
        issues = na._check_filename("BadName.py", "python", rule)
        assert issues, "安全的 naming pattern 被守卫误伤, 命名检查形同虚设"

    def test_naming_identifier_kind_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts import naming_analyzer as na

        calls = self._spy(monkeypatch, na)
        rule = {"pattern": self.DANGER}
        assert na._check_identifier_kind([(1, self.HOSTILE)], "python", "function", rule, "a.py") == []
        assert any(c[2] for c in calls), "naming/<kind> 未接入守卫"

    def test_lsp_text_to_range_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts.rules_engine import lsp_server as ls

        calls = self._spy(monkeypatch, ls)
        # 该函数首行有 `if not HAS_PYGLS: return None`, 无 pygls 时走不到守卫。
        monkeypatch.setattr(ls, "HAS_PYGLS", True)
        ls._text_to_range(self.HOSTILE, self.DANGER)
        assert any(c[2] for c in calls), "lsp/_text_to_range 未接入守卫"

    def test_lsp_get_rule_for_line_guarded(self, monkeypatch: Any, tmp_path: Any) -> None:
        """规则查找会 load_rules_for_language, 打桩掉以隔离外部依赖。"""
        from tools.scripts.rules_engine import lsp_server as ls

        calls = self._spy(monkeypatch, ls)
        rule = {"pattern": self.DANGER}
        monkeypatch.setattr(
            "tools.scripts.rules_engine.rule_loader.load_rules_for_language",
            lambda lang, rd=None: {"anti_patterns": [rule]},
        )
        ls._get_rule_for_line(self.HOSTILE, "python")
        assert any(c[2] for c in calls), "lsp/_get_rule_for_line 未接入守卫"


class TestCategoryShorthandsAreUnderstood:
    r"""`\w` / `\d` / `\s` 简写必须被正确展开。

    不支持时 `_in_first_set` 返回 None, 判定一律保守判危险 —— 实测把真实规则
    `@\w+(?:\.\w+)*\.ignore` (装饰器命名) 误判, 静默禁用整条命名检查。
    """

    @pytest.mark.parametrize(
        "pattern",
        [
            r"@\w+(?:\.\w+)*\.ignore",
            r"(?:\.\w+)*",
            r"(?:\w+\.)*",
            r"(?:\w+\.)*\w+",
            r"\b\w+\b",
        ],
    )
    def test_safe(self, pattern: str) -> None:
        assert _is_dangerous(pattern) is False, f"{pattern!r} 被误判为危险"

    @pytest.mark.parametrize("pattern", [r"(\w+)*$", r"(\d+)+$", r"(\s*)*$"])
    def test_still_catches_nested_categories(self, pattern: str) -> None:
        assert _is_dangerous(pattern) is True, f"{pattern!r} 是真实嵌套量词, 不得漏判"


class TestUniqueSplitNeedsBothDirections:
    r"""内层量词的分界既可能由**后继**钉死, 也可能由**前驱**钉死。

    ``(?:\.\w+)*`` 每次迭代必以 `\.` 开头 —— 迭代边界由 `.` 的位置唯一确定。
    只检查后继会把它误判为危险。仅看后继时该规则曾使 34 个测试变红。
    """

    def test_predecessor_pins_the_split(self) -> None:
        assert _is_dangerous(r"(?:\.\w+)*") is False

    def test_successor_pins_the_split(self) -> None:
        assert _is_dangerous(r"(?:\w+\.)*") is False

    def test_neither_side_pins_it(self) -> None:
        """两侧都没有钉子时仍须判危险 —— 这正是 ReDoS 的成因。"""
        assert _is_dangerous(r"(?:\w+)*") is True


class TestValidateRuleTestsIsGuarded:
    """validate_rule_tests 编译规则 pattern 并搜同一份 yml 里的 test_cases 代码。

    这是**双向**受控: pattern 与被匹配的 code 都来自 rules_dir 下的规则 yml,
    PR 场景由外部贡献者同时提供。实测撤掉守卫后, 一条 `(x|xx)+$` + 40 字符
    code 的规则可让该工具挂死 (>400s 未返回); 接上守卫后同一输入 0.09s 返回。

    夹具刻意用**短** payload (`xxxx!`): 指数级回溯需要长度才爆发。守卫在位时
    直接跳过; 守卫被撤掉时 2^4 的代价可忽略, 用例随即**失败**而非挂死 ——
    挂死无法与真实卡死区分, 那样这条用例就白写了。
    """

    EVIL_YML = """anti_patterns:
  - id: evil-dup-alt
    name: Evil
    severity: error
    category: security
    pattern: '(x|xx)+$'
    message: evil
    test_cases:
      - code: 'xxxx!'
        should_match: true
"""

    @staticmethod
    def _rules_root(tmp_path: Path) -> Path:
        """复刻 _load_rules_with_tests 的路径拼法: <rules_dir>/languages/<lang>/rules.d/。"""
        d = tmp_path / "languages" / "python" / "rules.d"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @pytest.fixture
    def evil_rule(self, tmp_path: Path) -> Path:
        target = self._rules_root(tmp_path) / "_tmp_evil_probe.yml"
        target.write_text(self.EVIL_YML, encoding="utf-8")
        return target

    def test_evil_pattern_is_skipped_fast(self, tmp_path: Path, monkeypatch: Any, evil_rule: Path) -> None:
        """必须跳过并报出, 且**快速**返回 —— 这里不设长超时, 挂死即测试失败。"""
        from tools.scripts import validate_rule_tests as vrt

        assert evil_rule.exists(), "恶意规则夹具未写入"
        monkeypatch.setattr(vrt, "_rules_dir", lambda: tmp_path)

        passed, failed, errors = vrt.validate_rule_tests("python")

        # 夹具里只有恶意规则, 正确行为是"跳过并计入 failed", 因此 passed 应为 0
        assert failed == 1, f"恶意规则应被记为失败: {errors}"
        assert passed == 0, "被跳过的规则不得计入通过"
        assert any("灾难性回溯" in e for e in errors), f"未报出跳过原因: {errors}"

    def test_guard_is_actually_consulted(self, tmp_path: Path, monkeypatch: Any, evil_rule: Path) -> None:
        """断言守卫被询问过, 而非仅靠"恰好没匹配上"。"""
        from tools.scripts import validate_rule_tests as vrt

        monkeypatch.setattr(vrt, "_rules_dir", lambda: tmp_path)
        calls: list[str] = []
        real = vrt.guard_pattern
        monkeypatch.setattr(vrt, "guard_pattern", lambda p, ctx="": calls.append(p) or real(p, ctx))

        vrt.validate_rule_tests("python")

        assert any("(x|xx)+$" in c for c in calls), "守卫未被询问"

    def test_legitimate_rules_still_validated(self, tmp_path: Path, monkeypatch: Any) -> None:
        """反向约束: 正常规则必须照常被校验 (守卫不得误伤真实规则)。"""
        from tools.scripts import validate_rule_tests as vrt

        good = self._rules_root(tmp_path) / "_tmp_good_probe.yml"
        good.write_text(
            "anti_patterns:\n"
            "  - id: good-rule\n"
            "    name: Good\n"
            "    severity: error\n"
            "    category: security\n"
            r"    pattern: 'password\s*='" + "\n"
            "    message: m\n"
            "    test_cases:\n"
            "      - code: 'password = \"x\"'\n"
            "        should_match: true\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(vrt, "_rules_dir", lambda: tmp_path)

        passed, failed, errors = vrt.validate_rule_tests("python")

        assert passed == 1, f"正常规则未被校验通过: failed={failed} errors={errors}"
        assert not any("灾难性回溯" in e for e in errors)
        good.unlink(missing_ok=True)


class TestWiringCoversFixPaths:
    """改写/替换类路径的接线 —— 审计第 4 轮才发现的三处。

    前三轮分别遗漏了 lsp/naming、validate_rule_tests、本组, 说明手工枚举不收敛。
    共同点: pattern 与被匹配的文本**都**来自外部 (规则 yml + 源码), 且这些路径
    还会**改写文件**, 挂死的代价高于纯只读检查。
    """

    DANGER = r"(x|xx)+$"
    # 短输入: 指数回溯需长度才爆发。守卫在位时直接跳过; 被撤掉时 2^4 代价可忽略,
    # 用例随即**失败**而非挂死 —— 挂死无法与真实卡死区分, 那样用例就白写了。
    HOSTILE = "xxx!"

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

    def test_fix_applier_guarded(self, monkeypatch: Any) -> None:
        from tools.scripts import fix_applier

        calls = self._spy(monkeypatch, fix_applier)
        result = fix_applier._parse_regex_replacement(f"s/{self.DANGER}/x/", self.HOSTILE)
        assert any(c[2] for c in calls), "fix_applier 未接入守卫"
        assert result is None, "危险 pattern 不得被真正执行"

    def test_ai_recommender_guarded(self, monkeypatch: Any, tmp_path: Path) -> None:
        import tools.ai_recommender as rec

        calls = self._spy(monkeypatch, rec)
        monkeypatch.setattr(
            rec,
            "CODE_SMELL_PATTERNS",
            {"python": [{"pattern": self.DANGER, "recommendation": "r", "reason": "x"}]},
        )
        rec.analyze_code_patterns(tmp_path / "a.py", self.HOSTILE, "python")
        assert any(c[2] for c in calls), "ai_recommender 未接入守卫"

    def test_fix_engine_guarded(self, monkeypatch: Any) -> None:
        import tools.fix_engine as fe

        calls = self._spy(monkeypatch, fe)
        engine = fe.FixEngine({"python": {self.DANGER: {"pattern": self.DANGER, "replacement": "y"}}})
        engine.fix_content(self.HOSTILE, "python", dry_run=True)
        assert any(c[2] for c in calls), "fix_engine 未接入守卫"
