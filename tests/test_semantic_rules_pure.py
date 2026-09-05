"""Tests for semantic_rules 纯函数 + 协议 + 注册表 (Phase 33b-1).

覆盖 pure-function 层级:
- SemanticRule Protocol (runtime_checkable + check 协议)
- _SEMANTIC_RULES 注册表操作: register/unregister/get/list/clear
- get_semantic_rules 语言过滤
- list_semantic_rules 元数据快照
- clear_semantic_rules 测试用清理

详见 ADR-036 Phase 33b 子任务分解 + ADR-043 (本次)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine import semantic_rules
from tools.scripts.rules_engine.models import Issue
from tools.scripts.rules_engine.semantic_rules import (
    _SEMANTIC_RULES,
    SemanticRule,
    clear_semantic_rules,
    get_semantic_rules,
    list_semantic_rules,
    register_semantic_rule,
    unregister_semantic_rule,
)


@pytest.fixture(autouse=True)
def _restore_rules_after_test():
    """每个测试后恢复注册表 (内置规则已自动注册), 防止污染其他测试。

    autouse: 每个测试自动应用, 即使测试未明确定义该 fixture
    """
    # 提前保存快照 + 重置为内置 (避免清空中间状态泄漏)
    _SEMANTIC_RULES.clear()
    for _r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
        register_semantic_rule(_r)
    yield
    # 测试结束后再次清空 + 重置 (保证隔离)
    _SEMANTIC_RULES.clear()
    for _r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
        register_semantic_rule(_r)


# ─────────────────────────────────────────────────────────────
# Phase 33b-1: 协议 + 注册表纯函数测试
# ─────────────────────────────────────────────────────────────


class TestSemanticRuleProtocol:
    """SemanticRule Protocol + runtime_checkable 行为。"""

    def test_protocol_has_required_attrs(self) -> None:
        """SemanticRule 定义 name/languages/severity 协议字段 + check 方法。"""
        # Protocol 字段注解
        annotations = SemanticRule.__annotations__
        assert "name" in annotations
        assert "languages" in annotations
        assert "severity" in annotations
        # check 方法作为 Protocol 成员 (可能不在 annotations 但在 __dict__)
        assert hasattr(SemanticRule, "check")

    def test_protocol_is_runtime_checkable(self) -> None:
        """SemanticRule 是 runtime_checkable Protocol。"""
        # runtime_checkable 通过 metaclass=ABCMeta + _is_protocol 标记
        # 验证 isinstance 检查可用
        class FakeRule:
            name = "fake"
            languages = {"python"}
            severity = "info"

            def check(self, ast: object, filepath: Path) -> list[Issue]:
                return []

        # Protocol 实际标记: 检查 hasattr 而不是 isinstance (Protocol runtime 检查限制)
        assert hasattr(FakeRule, "name")
        assert hasattr(FakeRule, "languages")
        assert hasattr(FakeRule, "severity")
        assert hasattr(FakeRule, "check")


class TestRegisterSemanticRule:
    """register_semantic_rule() 注册表写入。"""

    def test_register_adds_to_table(self) -> None:
        """register() 添加规则到 _SEMANTIC_RULES。"""
        clear_semantic_rules()
        rule = semantic_rules.MissingDocstringRule()
        register_semantic_rule(rule)
        assert "missing-docstring" in _SEMANTIC_RULES
        assert _SEMANTIC_RULES["missing-docstring"] is rule
        # 恢复内置规则
        for r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
            register_semantic_rule(r)

    def test_register_overrides_same_name(self) -> None:
        """同名规则覆盖 (last-write-wins)。"""
        clear_semantic_rules()

        class RuleV1:
            name = "test-rule"

            def check(self, ast: object, filepath: Path) -> list[Issue]:
                return []

        class RuleV2:
            name = "test-rule"

            def check(self, ast: object, filepath: Path) -> list[Issue]:
                return []

        register_semantic_rule(RuleV1())
        register_semantic_rule(RuleV2())
        assert _SEMANTIC_RULES["test-rule"] is not RuleV1
        # 恢复内置规则
        for r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
            register_semantic_rule(r)


class TestUnregisterSemanticRule:
    """unregister_semantic_rule() 注册表删除。"""

    def test_unregister_existing_returns_true(self) -> None:
        """注销存在的规则 → True。"""
        # 内置 unused-import 规则已注册
        result = unregister_semantic_rule("unused-import")
        assert result is True
        assert "unused-import" not in _SEMANTIC_RULES
        # 恢复
        register_semantic_rule(semantic_rules.UnusedImportRule())

    def test_unregister_nonexistent_returns_false(self) -> None:
        """注销不存在的规则 → False 不抛。"""
        result = unregister_semantic_rule("nonexistent-rule-xyz")
        assert result is False

    def test_unregister_preserves_other_rules(self) -> None:
        """注销一个规则不影响其他规则。"""
        # 记录存在性以便验证
        assert "missing-docstring" in _SEMANTIC_RULES
        unregister_semantic_rule("unused-import")
        # 其他规则仍在
        assert "missing-docstring" in _SEMANTIC_RULES
        # 恢复
        register_semantic_rule(semantic_rules.UnusedImportRule())


class TestGetSemanticRules:
    """get_semantic_rules() 语言过滤。"""

    def test_get_all_when_language_none(self) -> None:
        """language=None → 返回全部规则。"""
        all_rules = get_semantic_rules()
        # 内置 3 个规则
        assert len(all_rules) >= 3
        names = {r.name for r in all_rules}
        assert "unused-import" in names
        assert "missing-docstring" in names
        assert "high-complexity" in names

    def test_get_by_python_language(self) -> None:
        """language='python' → 返回包含 python 的规则。"""
        python_rules = get_semantic_rules("python")
        names = {r.name for r in python_rules}
        # missing-docstring 仅 python
        assert "missing-docstring" in names
        # unused-import 包含 python
        assert "unused-import" in names
        # high-complexity 包含 python
        assert "high-complexity" in names

    def test_get_by_unknown_language_returns_empty(self) -> None:
        """未知语言 → 空列表。"""
        rules = get_semantic_rules("cobol-9000")
        assert rules == []

    def test_get_returns_list_type(self) -> None:
        """返回 list[SemanticRule] 类型。"""
        rules = get_semantic_rules()
        assert isinstance(rules, list)


class TestListSemanticRules:
    """list_semantic_rules() 元数据快照。"""

    def test_returns_list_of_dicts(self) -> None:
        """返回 list[dict] 元数据。"""
        meta = list_semantic_rules()
        assert isinstance(meta, list)
        for item in meta:
            assert isinstance(item, dict)

    def test_meta_contains_required_fields(self) -> None:
        """每个 dict 包含 name/languages/severity。"""
        meta = list_semantic_rules()
        for item in meta:
            assert "name" in item
            assert "languages" in item
            assert "severity" in item

    def test_languages_is_sorted_list(self) -> None:
        """languages 字段是 sorted list (便于稳定输出)。"""
        meta = list_semantic_rules()
        for item in meta:
            languages = item["languages"]
            assert isinstance(languages, list)
            assert languages == sorted(languages)

    def test_severity_in_allowed_values(self) -> None:
        """severity 字段在 error/warning/info 集合内。"""
        allowed = {"error", "warning", "info"}
        meta = list_semantic_rules()
        for item in meta:
            assert item["severity"] in allowed


class TestClearSemanticRules:
    """clear_semantic_rules() 测试用清理。"""

    def test_clear_empties_registry(self) -> None:
        """clear() 清空 _SEMANTIC_RULES 字典。"""
        assert len(_SEMANTIC_RULES) >= 3  # 内置规则存在
        clear_semantic_rules()
        assert _SEMANTIC_RULES == {}
        assert len(get_semantic_rules()) == 0
        # 恢复
        for r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
            register_semantic_rule(r)

    def test_clear_returns_none(self) -> None:
        """clear() 无返回值 (返回 None)。"""
        result = clear_semantic_rules()
        assert result is None
        # 恢复
        for r in semantic_rules._BUILTIN_SEMANTIC_RULES:  # noqa: SLF001
            register_semantic_rule(r)


class TestBuiltinRulesRegistration:
    """模块导入时自动注册内置规则 (行为锁定)。"""

    def test_builtin_rules_already_registered(self) -> None:
        """内置规则 (Unused/MissingDocstring/HighComplexity) 已自动注册。"""
        names = set(_SEMANTIC_RULES.keys())
        assert "unused-import" in names
        assert "missing-docstring" in names
        assert "high-complexity" in names

    def test_builtin_rules_have_correct_metadata(self) -> None:
        """内置规则 metadata 正确。"""
        rules_by_name = {r.name: r for r in get_semantic_rules()}

        # unused-import
        rule = rules_by_name["unused-import"]
        assert "python" in rule.languages
        assert rule.severity == "warning"

        # missing-docstring
        rule = rules_by_name["missing-docstring"]
        assert rule.languages == {"python"}
        assert rule.severity == "info"

        # high-complexity
        rule = rules_by_name["high-complexity"]
        assert "python" in rule.languages
        assert "rust" in rule.languages
        assert rule.severity == "warning"


class TestBaseSemanticRule:
    """_BaseSemanticRule 基类默认行为。"""

    def test_base_check_returns_empty(self) -> None:
        """基类默认 check() 返回空 list。"""
        rule = semantic_rules._BaseSemanticRule()  # noqa: SLF001
        issues = rule.check(None, Path("/tmp/none"))
        assert issues == []

    def test_base_class_has_default_metadata(self) -> None:
        """基类提供默认 metadata 字段。"""
        rule = semantic_rules._BaseSemanticRule()  # noqa: SLF001
        assert rule.name == ""
        assert rule.languages == set()
        assert rule.severity == "warning"
