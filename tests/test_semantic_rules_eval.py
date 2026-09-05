"""Tests for semantic_rules 内置规则 check() + run_semantic_rules() (Phase 33b-2).

覆盖 rule eval 层:
- UnusedImportRule.check(): 未用 from import 检测 (含边界)
- MissingDocstringRule.check(): 公开函数缺 docstring 检测
- HighComplexityRule.check(): 圈复杂度 > 10 检测
- run_semantic_rules(): 多规则调度 + enabled_rules 过滤 + 异常隔离

详见 ADR-036 Phase 33b 子任务分解 + ADR-044 (本次)。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.scripts.rules_engine import semantic_rules
from tools.scripts.rules_engine.semantic_rules import (
    HighComplexityRule,
    MissingDocstringRule,
    UnusedImportRule,
    run_semantic_rules,
)


def _make_imp(
    module: str = "os",
    names: list[str] | None = None,
    line: int = 1,
    is_from: bool = True,
) -> SimpleNamespace:
    """构造 import 桩对象 (duck typing)。"""
    return SimpleNamespace(module=module, names=names or [], line=line, is_from=is_from, level=0)


def _make_func(
    name: str = "func",
    line: int = 1,
    docstring: str | None = "fake",
    complexity: int = 1,
) -> SimpleNamespace:
    """构造 function 桩对象 (duck typing)。"""
    return SimpleNamespace(name=name, line=line, docstring=docstring, complexity=complexity)


@pytest.fixture(autouse=True)
def _restore_rules_after_test():
    """保证测试间注册表隔离。"""
    from tools.scripts.rules_engine.semantic_rules import (
        _SEMANTIC_RULES,
        register_semantic_rule,
    )

    _SEMANTIC_RULES.clear()
    for r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
        register_semantic_rule(r)
    yield
    _SEMANTIC_RULES.clear()
    for r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
        register_semantic_rule(r)


# ─────────────────────────────────────────────────────────────
# Phase 33b-2: 规则 eval 层
# ─────────────────────────────────────────────────────────────


class TestUnusedImportRule:
    """UnusedImportRule.check(): from-import 未使用检测。"""

    def test_no_imports_returns_empty(self, tmp_path: Path) -> None:
        """无 import → 不发 issue。"""
        rule = UnusedImportRule()
        file_obj = SimpleNamespace(imports=[])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_ast_without_imports_attr_returns_empty(self, tmp_path: Path) -> None:
        """AST 无 imports 属性 (例如 dataclass) → 返回空不抛。"""
        rule = UnusedImportRule()
        # 不是 SimpleNamespace 不带 imports 属性
        file_obj = object()
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_unused_from_import_emits_issue(self, tmp_path: Path) -> None:
        """from X import Y 但 Y 未在文件使用 → 发 issue。"""
        rule = UnusedImportRule()
        file_obj = SimpleNamespace(imports=[_make_imp("os", ["path"], line=1, is_from=True)])
        f = tmp_path / "f.py"
        # 文件中不含 'path' (除了 import 语句本身)
        f.write_text("import other_module\nx = 1\n")
        issues = rule.check(file_obj, f)
        assert len(issues) == 1
        assert issues[0].rule_id == "semantic-unused-import"
        assert "path" in issues[0].message

    def test_used_import_no_issue(self, tmp_path: Path) -> None:
        """from X import Y, Y 被使用 → 不发 issue。"""
        rule = UnusedImportRule()
        file_obj = SimpleNamespace(imports=[_make_imp("os", ["path"], line=1, is_from=True)])
        f = tmp_path / "f.py"
        f.write_text("from os import path\nx = path.join('a', 'b')\n")
        issues = rule.check(file_obj, f)
        assert issues == []

    def test_non_from_import_skipped(self, tmp_path: Path) -> None:
        """非 from import (import X) → 跳过 (本规则仅查 from)。"""
        rule = UnusedImportRule()
        file_obj = SimpleNamespace(imports=[_make_imp("os", [], line=1, is_from=False)])
        f = tmp_path / "f.py"
        f.write_text("import os\n")
        issues = rule.check(file_obj, f)
        assert issues == []

    def test_star_import_skipped(self, tmp_path: Path) -> None:
        """from X import * → 跳过 (无法静态判断)。"""
        rule = UnusedImportRule()
        file_obj = SimpleNamespace(imports=[_make_imp("os", ["*"], line=1, is_from=True)])
        f = tmp_path / "f.py"
        f.write_text("from os import *\n")
        issues = rule.check(file_obj, f)
        assert issues == []

    def test_read_text_os_error_returns_empty(self, tmp_path: Path) -> None:
        """read_text OSError → 返回空 (不抛)。"""
        rule = UnusedImportRule()
        file_obj = SimpleNamespace(imports=[_make_imp("os", ["path"], line=1, is_from=True)])
        nonexistent = tmp_path / "nonexistent.py"
        issues = rule.check(file_obj, nonexistent)
        assert issues == []


class TestMissingDocstringRule:
    """MissingDocstringRule.check(): 公开函数缺 docstring 检测。"""

    def test_no_functions_returns_empty(self, tmp_path: Path) -> None:
        """无 functions → 不发 issue。"""
        rule = MissingDocstringRule()
        file_obj = SimpleNamespace(functions=None)
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_public_function_no_docstring_emits_issue(self, tmp_path: Path) -> None:
        """公开函数无 docstring → 发 issue。"""
        rule = MissingDocstringRule()
        file_obj = SimpleNamespace(functions=[_make_func(name="public_func", docstring=None)])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert len(issues) == 1
        assert issues[0].rule_id == "semantic-missing-docstring"
        assert issues[0].severity == "info"
        assert "public_func" in issues[0].message

    def test_private_function_skipped(self, tmp_path: Path) -> None:
        """私有函数 (下划线开头) → 跳过不发 issue。"""
        rule = MissingDocstringRule()
        file_obj = SimpleNamespace(functions=[_make_func(name="_private", docstring=None)])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_documented_function_no_issue(self, tmp_path: Path) -> None:
        """公开函数有 docstring → 不发 issue。"""
        rule = MissingDocstringRule()
        file_obj = SimpleNamespace(functions=[_make_func(name="public_func", docstring="I have docs")])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_mixed_functions(self, tmp_path: Path) -> None:
        """混合: 私有 + 公开有 docs + 公开无 docs → 仅最后一个发 issue。"""
        rule = MissingDocstringRule()
        file_obj = SimpleNamespace(
            functions=[
                _make_func(name="_private", docstring=None),
                _make_func(name="documented", docstring="has docs"),
                _make_func(name="undocumented", docstring=None),
            ]
        )
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert len(issues) == 1
        assert "undocumented" in issues[0].message


class TestHighComplexityRule:
    """HighComplexityRule.check(): 圈复杂度 > 10 检测。"""

    def test_no_functions_returns_empty(self, tmp_path: Path) -> None:
        """无 functions → 不发 issue。"""
        rule = HighComplexityRule()
        file_obj = SimpleNamespace(functions=None)
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_low_complexity_no_issue(self, tmp_path: Path) -> None:
        """complexity <= 10 → 不发 issue。"""
        rule = HighComplexityRule()
        file_obj = SimpleNamespace(functions=[_make_func(name="simple", complexity=5)])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []

    def test_high_complexity_emits_issue(self, tmp_path: Path) -> None:
        """complexity > 10 → 发 issue。"""
        rule = HighComplexityRule()
        file_obj = SimpleNamespace(functions=[_make_func(name="complex_func", complexity=15)])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert len(issues) == 1
        assert issues[0].rule_id == "semantic-high-complexity"
        assert "complex_func" in issues[0].message
        assert "15" in issues[0].message

    def test_complexity_threshold_is_10(self, tmp_path: Path) -> None:
        """complexity 边界: 10 不发, 11 发。"""
        rule = HighComplexityRule()
        # boundary
        file_obj = SimpleNamespace(functions=[_make_func(name="boundary", complexity=10)])
        assert rule.check(file_obj, tmp_path / "f.py") == []
        file_obj = SimpleNamespace(functions=[_make_func(name="boundary", complexity=11)])
        assert len(rule.check(file_obj, tmp_path / "f.py")) == 1

    def test_complexity_none_treated_as_one(self, tmp_path: Path) -> None:
        """complexity=None → getattr 默认 1, 不发 issue。"""
        rule = HighComplexityRule()
        func = SimpleNamespace(name="f", line=1, docstring=None, complexity=None)
        file_obj = SimpleNamespace(functions=[func])
        issues = rule.check(file_obj, tmp_path / "f.py")
        assert issues == []


class TestRunSemanticRules:
    """run_semantic_rules(): 多规则调度 + enabled_rules + 异常隔离。"""

    def test_run_with_no_matching_language(self, tmp_path: Path) -> None:
        """language 无匹配规则 → 返回空。"""
        file_obj = SimpleNamespace(imports=[], functions=[])
        issues = run_semantic_rules(file_obj, tmp_path / "f.py", language="cobol-9000")
        assert issues == []

    def test_run_python_matches_all_builtin(self, tmp_path: Path) -> None:
        """language='python' 触发所有内置规则。"""
        # 构造 1 unused import + 1 public func no docstring + 1 high complexity
        file_obj = SimpleNamespace(
            imports=[_make_imp("os", ["unused_path"], line=1, is_from=True)],
            functions=[
                _make_func(name="public_func", docstring=None),
                _make_func(name="complex_func", complexity=15),
            ],
        )
        f = tmp_path / "f.py"
        f.write_text("from os import unused_path\n")
        issues = run_semantic_rules(file_obj, f, language="python")
        rule_ids = {i.rule_id for i in issues}
        # 3 个内置规则都应触发
        assert "semantic-unused-import" in rule_ids
        assert "semantic-missing-docstring" in rule_ids
        assert "semantic-high-complexity" in rule_ids

    def test_run_with_enabled_rules_filter(self, tmp_path: Path) -> None:
        """enabled_rules 仅运行指定规则。"""
        file_obj = SimpleNamespace(
            imports=[_make_imp("os", ["unused_path"], line=1, is_from=True)],
            functions=[
                _make_func(name="public_func", docstring=None),
            ],
        )
        f = tmp_path / "f.py"
        f.write_text("from os import unused_path\n")
        # 仅运行 unused-import
        issues = run_semantic_rules(file_obj, f, language="python", enabled_rules={"unused-import"})
        rule_ids = {i.rule_id for i in issues}
        assert rule_ids == {"semantic-unused-import"}

    def test_rule_exception_does_not_break_pipeline(self, tmp_path: Path, monkeypatch) -> None:
        """单条规则抛异常 → 不阻断其他规则。"""

        # 让 MissingDocstringRule.check 抛异常
        def _raise(self, file, filepath):
            raise ValueError("boom")

        monkeypatch.setattr(MissingDocstringRule, "check", _raise)

        file_obj = SimpleNamespace(
            functions=[_make_func(name="public_func", docstring=None)],
        )
        issues = run_semantic_rules(file_obj, tmp_path / "f.py", language="python")
        # 异常被吞, 返回空 (其他规则也无 issue)
        assert issues == []

    def test_run_returns_issue_list(self, tmp_path: Path) -> None:
        """返回 list[Issue] 类型。"""
        file_obj = SimpleNamespace(imports=[], functions=[])
        issues = run_semantic_rules(file_obj, tmp_path / "f.py", language="python")
        assert isinstance(issues, list)
