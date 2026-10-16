"""ReDoS 守卫的结构性回归: 声明式清单 + 误报不变量。

## 为什么是"声明式清单"而不是自动检测

守卫是**手工接线**的, 手工枚举已被证明不收敛 —— 本次会话四轮审计分别遗漏了
lsp/naming、validate_rule_tests、fix_applier/ai_recommender/fix_engine, 每轮都是
"再搜一遍"才发现下一批, 且**漏了没有任何东西会失败**。

自然的做法是写一个自动检测: 扫描出"读规则配置且执行正则"的模块, 要求其接入守卫。
**这个做法经实测不可行**, 两难如下 (数字来自本仓库当前状态):

| 判定条件 | 漏报 (真实危险却未被检出) | 误报 (实际硬编码却被要求接线) |
|---|---|---|
| 仅"调用规则加载器" | 7 | 0 |
| 再加 `rule`/`rules` 等形参名 | 3 | 5 |

漏报是结构性的: `adg_cli/check.py`、`fix_applier` 等模块**由调用方注入**已加载的
规则, 自己并不调用任何加载器。误报是因为 `rule`/`rules` 这类名字过于普遍, 会命中
`ast_fixer`、`auto_fix`、`hallucination_detector` 等纯字面量模块。

更糟的是维护后果: 持续误报的检测器会诱使人把**真实**案例也加进白名单, 从而彻底
失效。故此处只做两件**能机械判定**的事:

1. **清单回归**: 清单内每个模块必须仍有守卫 —— 防止守卫被误删。
2. **误报不变量**: 守卫不得误伤真实规则语料 —— 防止接线变成"静默禁用规则"。

全仓普查(人工一次, 54 处)改变了这个前提, 使其中一类可机械保证:

`TestGuardedModulesLeaveNoUnwiredSite` 断言**已接线模块内每个动态正则点之前都有
守卫**。它不做任何"该模块是否读配置"的推断 —— 那正是上表失败的地方; 它只做纯
AST 可判定的事(枚举 pattern 非字面量的 `re.*` 点, 比较行号)。因此不需要例外
清单, 也就不会重蹈"持续误报 -> 真实案例被加进白名单 -> 检测器彻底失效"的覆辙。

覆盖的失败模式是 `tools/scripts/auto_fix.py`: 该文件早已接线, 后来又新增第二个
config 驱动的正则点(`_apply_all_rules`)未补守卫, 逐点审计连续两轮漏检, 因为
"多了一个点"没有任何东西会报告。现在会。

仍然无法机械保证的: 在**尚未接线**的模块里新增点(需人工决定该模块是否读配置,
这正是上表失败之处)。清单把已知面固定下来, 使新增成为显式的清单变更。

## 白名单的成立依据会被持续验证

`ALLOWLIST` 里的模块满足"读配置 + 执行正则"但 pattern 全为源码字面量。
`test_allowlist_entries_are_actually_hardcoded` 断言其每个匹配点的 arg0 是
`ast.Constant` —— 若将来有人把某个 pattern 改成从配置读取, 该用例立即失败,
迫使其重新评估, 而非静默沿用旧豁免。
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# module path -> 该模块内 guard_pattern 的最小出现次数
# 次数写具体值而非 >=1: 若某模块新增了第二个 config 驱动的正则点却忘了接线,
# 断言会因"次数不足"而失败, 从而把"新增即需评估"变成机械不变量。
GUARDED_MODULES: dict[str, int] = {
    "tools/scripts/adg_cli/check.py": 4,
    "tools/scripts/rules_engine/anti_pattern_checker.py": 4,
    "tools/scripts/rules_engine/lsp_server.py": 3,
    "tools/scripts/naming_analyzer.py": 2,
    "tools/scripts/rules_engine/validators/pipeline.py": 1,
    "tools/scripts/validate_rule_tests.py": 1,
    "tools/scripts/fix_applier.py": 1,
    "tools/ai_recommender/__init__.py": 1,
    "tools/fix_engine/__init__.py": 1,
    # 注意与 tools/scripts/rules_engine/auto_fix.py 区分: 那个文件的 pattern 全部
    # 来自硬编码的 FIX_PATTERNS, 无需守卫; 本文件把 issue.rule_id 当正则用, 而
    # rule_id 来自规则配置, 且替换结果会写回文件。
    "tools/scripts/auto_fix.py": 2,
    # 载入点闸门: 一次拦截, 下游 60+ 处 config-regex 调用点自动免疫
    "tools/scripts/rules_engine/rule_loader.py": 1,
}

# 读配置 + 执行正则, 但 pattern 为源码字面量 -> 不要求守卫。必须写明理由。
ALLOWLIST: dict[str, str] = {
    "tools/scripts/rules_engine/rule_docs_mapper.py": (
        "解析文档 frontmatter/标题, 正则为源码字面量; 匹配对象是仓库内文档而非规则配置"
    ),
    "tools/scripts/validate_agent_definition.py": (
        "校验 agent 定义 frontmatter, 9 处正则全为源码字面量; 虽读 yaml 但不取其中正则"
    ),
}

MATCH_FUNCS = frozenset({"search", "finditer", "match", "sub", "subn", "fullmatch"})


def _count_guard_calls(path: Path) -> int:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # guard_pattern 既可能以裸名调用 (直接 import), 也可能是 re.guard_pattern
        if isinstance(func, ast.Name) and func.id == "guard_pattern":
            count += 1
        elif isinstance(func, ast.Attribute) and func.attr == "guard_pattern":
            count += 1
    return count


class TestGuardInventory:
    @pytest.mark.parametrize("rel", sorted(GUARDED_MODULES))
    def test_module_still_guards(self, rel: str) -> None:
        """清单内模块必须仍有守卫, 且不得少于登记的次数。"""
        path = REPO_ROOT / rel
        assert path.is_file(), f"清单中的 {rel} 已不存在, 请更新 GUARDED_MODULES"
        expected = GUARDED_MODULES[rel]
        actual = _count_guard_calls(path)
        assert actual >= expected, (
            f"{rel}: 期望至少 {expected} 处 guard_pattern, 实际 {actual}。"
            "若新增了 config 驱动的正则点却未接线, 请补上; 若守卫被移除了, 请恢复。"
        )

    def test_guard_pattern_is_importable(self) -> None:
        from tools.scripts.rules_engine.regex_cache import guard_pattern

        assert callable(guard_pattern)

    def test_guard_returns_bool_for_dangerous_and_safe(self) -> None:
        from tools.scripts.rules_engine.regex_cache import guard_pattern

        assert guard_pattern(r"(a|aa)+$", "t") is True, "重复分支必须拦下"
        assert guard_pattern(r"\b\w+\b", "t") is False, "常见无害模式不得误伤"


class TestAllowlistIsJustified:
    @pytest.mark.parametrize("rel", sorted(ALLOWLIST))
    def test_allowlist_entry_exists(self, rel: str) -> None:
        assert (REPO_ROOT / rel).is_file(), f"ALLOWLIST 中的 {rel} 已不存在, 请移除该条目"
        assert ALLOWLIST[rel].strip(), "白名单条目必须写明理由"

    @pytest.mark.parametrize("rel", sorted(ALLOWLIST))
    def test_allowlist_entries_are_actually_hardcoded(self, rel: str) -> None:
        """白名单的成立依据: 每个匹配点的 arg0 必须是源码字面量。

        将来若有人把某个 pattern 改为从配置读取, 本用例失败, 迫使其重新评估
        是否需要守卫 —— 而非静默沿用旧豁免。
        """
        path = REPO_ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        dynamic: list[str] = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in MATCH_FUNCS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "re"
            ):
                continue
            if not node.args:
                continue
            if not isinstance(node.args[0], ast.Constant):
                dynamic.append(f"L{node.lineno}: {ast.unparse(node.args[0])[:50]}")
        assert not dynamic, f"{rel} 出现了 pattern 非字面量的 re 匹配点, 不能再豁免守卫:\n  " + "\n  ".join(dynamic)


class TestNoFalsePositiveOnRealCorpus:
    """接线不得变成"静默禁用真实规则"—— 那是另一种 fail-open。"""

    def test_real_rule_corpus_not_flagged(self) -> None:
        import yaml

        from tools.scripts.rules_engine.regex_cache import _is_dangerous

        patterns: set[str] = set()
        for yml in REPO_ROOT.glob("ai-dev-framework/**/*.yml"):
            try:
                data = yaml.safe_load(yml.read_text(encoding="utf-8"))
            except Exception:
                continue

            def walk(node: object) -> None:
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

        assert len(patterns) > 100, "语料采样异常, 本用例失去意义"
        flagged = [p for p in patterns if _is_dangerous(p)]
        rate = len(flagged) / len(patterns)
        assert rate < 0.02, f"误报率 {rate:.2%} 过高, 会静默丢弃过多真实规则: {flagged[:3]}"


@functools.lru_cache(maxsize=1)
def _iter_dynamic_sites() -> tuple[tuple[str, int, int], ...]:
    """枚举全仓 pattern 非字面量的 re.* 执行点。纯 AST, 不含任何推断。"""
    skip_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "build",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
    }
    out: list[tuple[str, int, int]] = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in MATCH_FUNCS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "re"
                and node.args
                and not (isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str))
            ):
                continue
            out.append((str(path.relative_to(REPO_ROOT)), node.lineno, id(node.args[0])))
    return tuple(out)


class TestGuardedModulesLeaveNoUnwiredSite:
    """已接线模块内, 动态正则点数不得超过守卫数。

    **不需要任何例外清单**, 因此不会像依赖推断的检测器那样腐烂(见文件开头:
    "持续误报的检测器会诱使人把真实案例也加进白名单")。

    捕获的失败模式正是 `tools/scripts/auto_fix.py` 那一类: 该文件已有守卫,
    后来又新增了第二个 config 驱动的正则点(_apply_all_rules)却未补守卫 ——
    逐点审计漏了两轮, 因为"多了一个点"没有任何东西会报告。本用例会立即失败。

    断言用 `<=` 而非 `==`: 一个守卫可以合法覆盖多个点(fix_engine 的 guard 在
    finditer 与 sub 之前 continue, 覆盖 2 个动态点)。
    """

    def test_census_is_non_trivial(self) -> None:
        sites = _iter_dynamic_sites()
        assert len(sites) > 20, f"普查只找到 {len(sites)} 个动态正则点, 采样异常, 本组用例失去意义"

    @pytest.mark.parametrize("rel", sorted(GUARDED_MODULES))
    def test_guarded_module_has_no_unwired_site(self, rel: str) -> None:
        """每个动态正则点都必须**位于某处守卫之后**。

        断言"守卫行号 < 使用行号", 而非"守卫数 >= 点数": 前者精确表达"用前先守",
        后者会把"一个守卫 continue 掉一整块"误判为漏接 —— fix_engine 的守卫在
        finditer 与 sub 之前 continue, 一处守卫合法覆盖 2 个点。
        """
        path = REPO_ROOT / rel
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            pytest.skip(f"{rel} 无法解析")
        guard_lines = sorted(
            n.lineno
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and (
                (isinstance(n.func, ast.Name) and n.func.id == "guard_pattern")
                or (isinstance(n.func, ast.Attribute) and n.func.attr == "guard_pattern")
            )
        )
        assert guard_lines, f"{rel} 已无任何守卫, 却仍在 GUARDED_MODULES 中"

        unwired = [
            f"L{lineno}"
            for rel_path, lineno, _ in _iter_dynamic_sites()
            if rel_path == rel and not any(g < lineno for g in guard_lines)
        ]
        assert not unwired, (
            f"{rel}: 以下动态正则点之前没有任何守卫: {unwired}。"
            "新增了 config 驱动的正则点却未接入守卫 —— 请在其之前补 guard_pattern "
            "(或证明该 pattern 外部不可控并移出 GUARDED_MODULES)。"
        )
