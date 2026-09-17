"""Tests for semantic_rules.py - AST-level semantic rule system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.scripts.rules_engine.models import Issue
from tools.scripts.rules_engine.semantic_rules import (
    _BUILTIN_SEMANTIC_RULES,
    _SEMANTIC_RULES,
    HighComplexityRule,
    MissingDocstringRule,
    SemanticRule,
    UnusedImportRule,
    clear_semantic_rules,
    get_semantic_rules,
    list_semantic_rules,
    register_semantic_rule,
    run_semantic_rules,
    unregister_semantic_rule,
)

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_rules():
    """每个测试前清空规则（保留内置规则重新注册）。"""
    original_rules = dict(_SEMANTIC_RULES)
    _SEMANTIC_RULES.clear()
    yield
    _SEMANTIC_RULES.clear()
    _SEMANTIC_RULES.update(original_rules)


@pytest.fixture
def mock_filepath(tmp_path: Path) -> Path:
    return tmp_path / "sample.py"


@pytest.fixture
def mock_ast_unused_import() -> MagicMock:
    """模拟包含未使用导入的 AST。"""
    imp = MagicMock()
    imp.is_from = True
    imp.module = "os"
    imp.names = ["path"]
    imp.line = 1

    mock = MagicMock()
    mock.imports = [imp]
    return mock


@pytest.fixture
def mock_ast_missing_docstring() -> MagicMock:
    """模拟缺少 docstring 的公开函数 AST。"""
    func = MagicMock()
    func.name = "public_func"
    func.docstring = None
    func.line = 10

    func_private = MagicMock()
    func_private.name = "_private_func"
    func_private.docstring = None
    func_private.line = 20

    mock = MagicMock()
    mock.functions = [func, func_private]
    return mock


@pytest.fixture
def mock_ast_high_complexity() -> MagicMock:
    """模拟高复杂度函数 AST。"""
    func = MagicMock()
    func.name = "complex_func"
    func.complexity = 15
    func.line = 5

    func_normal = MagicMock()
    func_normal.name = "normal_func"
    func_normal.complexity = 5
    func_normal.line = 15

    mock = MagicMock()
    mock.functions = [func, func_normal]
    return mock


# ─── Test SemanticRule Protocol ──────────────────────────────────────────────


def test_semantic_rule_protocol() -> None:
    """验证内置规则实现 SemanticRule Protocol。"""
    assert isinstance(UnusedImportRule(), SemanticRule)
    assert isinstance(MissingDocstringRule(), SemanticRule)
    assert isinstance(HighComplexityRule(), SemanticRule)


# ─── Test Registration ────────────────────────────────────────────────────────


def test_register_semantic_rule() -> None:
    """测试规则注册。"""

    class DummyRule:
        name = "dummy"
        languages = {"python"}
        severity = "info"

        def check(self, ast: object, filepath: Path) -> list[Issue]:
            return []

    rule = DummyRule()
    register_semantic_rule(rule)
    assert "dummy" in _SEMANTIC_RULES
    assert _SEMANTIC_RULES["dummy"] is rule


def test_register_overwrites_existing() -> None:
    """测试同名规则覆盖。"""

    class RuleV1:
        name = "test-rule"
        languages = {"python"}
        severity = "warning"

        def check(self, ast: object, filepath: Path) -> list[Issue]:
            return []

    class RuleV2:
        name = "test-rule"
        languages = {"python"}
        severity = "error"

        def check(self, ast: object, filepath: Path) -> list[Issue]:
            return []

    register_semantic_rule(RuleV1())
    assert _SEMANTIC_RULES["test-rule"].severity == "warning"
    register_semantic_rule(RuleV2())
    assert _SEMANTIC_RULES["test-rule"].severity == "error"


def test_unregister_semantic_rule() -> None:
    """测试规则注销。"""

    class TempRule:
        name = "temp"
        languages = set()
        severity = "info"

        def check(self, ast: object, filepath: Path) -> list[Issue]:
            return []

    register_semantic_rule(TempRule())
    assert unregister_semantic_rule("temp") is True
    assert "temp" not in _SEMANTIC_RULES
    # 注销不存在的规则返回 False
    assert unregister_semantic_rule("nonexistent") is False


def test_clear_semantic_rules() -> None:
    """测试清空所有规则。"""
    register_semantic_rule(
        type("R", (), {"name": "clearable", "languages": set(), "severity": "info", "check": lambda s, a, f: []})()
    )
    assert len(_SEMANTIC_RULES) >= 1
    clear_semantic_rules()
    assert len(_SEMANTIC_RULES) == 0


# ─── Test Getters ─────────────────────────────────────────────────────────────


def test_get_semantic_rules_all() -> None:
    """测试获取所有规则。"""
    for rule in _BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(rule)
    rules = get_semantic_rules()
    assert len(rules) == 3


def test_get_semantic_rules_filter_by_language() -> None:
    """测试按语言过滤规则。"""
    for rule in _BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(rule)
    py_rules = get_semantic_rules("python")
    assert all("python" in r.languages for r in py_rules)


def test_get_semantic_rules_no_match() -> None:
    """测试无匹配语言时返回空列表。"""
    for rule in _BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(rule)
    # 没有为 PHP 注册的规则
    php_rules = get_semantic_rules("php")
    assert len(php_rules) == 0


def test_list_semantic_rules() -> None:
    """测试列出规则元数据。"""
    for rule in _BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(rule)
    meta = list_semantic_rules()
    assert len(meta) == 3
    for m in meta:
        assert "name" in m
        assert "languages" in m
        assert "severity" in m


# ─── Test UnusedImportRule ───────────────────────────────────────────────────


def test_unused_import_rule_detects_unused(
    mock_ast_unused_import: MagicMock, mock_filepath: Path, tmp_path: Path
) -> None:
    """测试检测未使用导入。"""
    # 写入文件内容：只出现导入语句，没有实际使用
    (mock_filepath).write_text("from os import path\n", encoding="utf-8")

    rule = UnusedImportRule()
    issues = rule.check(mock_ast_unused_import, mock_filepath)

    assert len(issues) == 1
    assert issues[0].category == "unused-import"
    assert issues[0].rule_id == "semantic-unused-import"


def test_unused_import_rule_used_import(mock_filepath: Path, tmp_path: Path) -> None:
    """测试已使用的导入不报告。"""
    imp = MagicMock()
    imp.is_from = True
    imp.module = "os"
    imp.names = ["path"]
    imp.line = 1

    mock = MagicMock()
    mock.imports = [imp]

    # 文件内容显示 path 被使用
    mock_filepath.write_text("from os import path\npath.join('a', 'b')\n", encoding="utf-8")

    rule = UnusedImportRule()
    issues = rule.check(mock, mock_filepath)
    assert len(issues) == 0


def test_unused_import_rule_no_imports(mock_filepath: Path) -> None:
    """测试没有导入时返回空。"""
    rule = UnusedImportRule()
    mock = MagicMock()
    mock.imports = None
    issues = rule.check(mock, mock_filepath)
    assert len(issues) == 0


# ─── Test MissingDocstringRule ───────────────────────────────────────────────


def test_missing_docstring_rule_detects(mock_ast_missing_docstring: MagicMock, mock_filepath: Path) -> None:
    """测试检测缺少 docstring 的公开函数。"""
    rule = MissingDocstringRule()
    issues = rule.check(mock_ast_missing_docstring, mock_filepath)

    assert len(issues) == 1
    assert issues[0].category == "missing-docstring"
    assert issues[0].message == "Public function 'public_func' lacks a docstring"


def test_missing_docstring_rule_skips_private(mock_ast_missing_docstring: MagicMock, mock_filepath: Path) -> None:
    """测试跳过私有函数。"""
    rule = MissingDocstringRule()
    issues = rule.check(mock_ast_missing_docstring, mock_filepath)
    # 只应报告 public_func，_private_func 不应报告
    assert all("private" not in i.message for i in issues)


def test_missing_docstring_rule_no_functions(mock_filepath: Path) -> None:
    """测试没有函数时返回空。"""
    rule = MissingDocstringRule()
    mock = MagicMock()
    mock.functions = None
    issues = rule.check(mock, mock_filepath)
    assert len(issues) == 0


# ─── Test HighComplexityRule ─────────────────────────────────────────────────


def test_high_complexity_rule_detects(mock_ast_high_complexity: MagicMock, mock_filepath: Path) -> None:
    """测试检测高复杂度函数。"""
    rule = HighComplexityRule()
    issues = rule.check(mock_ast_high_complexity, mock_filepath)

    assert len(issues) == 1
    assert issues[0].category == "complexity"
    assert issues[0].rule_id == "semantic-high-complexity"
    assert "complex_func" in issues[0].message
    assert "15" in issues[0].message


def test_high_complexity_rule_no_functions(mock_filepath: Path) -> None:
    """测试没有函数时返回空。"""
    rule = HighComplexityRule()
    mock = MagicMock()
    mock.functions = None
    issues = rule.check(mock, mock_filepath)
    assert len(issues) == 0


def test_high_complexity_rule_normal_complexity(mock_filepath: Path) -> None:
    """测试正常复杂度函数不报告。"""
    func = MagicMock()
    func.name = "normal"
    func.complexity = 5
    func.line = 1

    mock = MagicMock()
    mock.functions = [func]

    rule = HighComplexityRule()
    issues = rule.check(mock, mock_filepath)
    assert len(issues) == 0


# ─── Test run_semantic_rules ──────────────────────────────────────────────────


def test_run_semantic_rules_all_rules(mock_filepath: Path, tmp_path: Path) -> None:
    """测试运行所有匹配的语义规则。"""
    for rule in _BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(rule)

    # 构造一个同时触发多条规则的 AST
    imp = MagicMock()
    imp.is_from = True
    imp.module = "os"
    imp.names = ["unused_name"]
    imp.line = 1

    func = MagicMock()
    func.name = "public_no_doc"
    func.docstring = None
    func.line = 5

    mock = MagicMock()
    mock.imports = [imp]
    mock.functions = [func]

    mock_filepath.write_text("from os import unused_name\n", encoding="utf-8")

    issues = run_semantic_rules(mock, mock_filepath, "python")

    categories = {i.category for i in issues}
    assert "unused-import" in categories
    assert "missing-docstring" in categories


def test_run_semantic_rules_filter_enabled(mock_filepath: Path, tmp_path: Path) -> None:
    """测试仅运行指定规则。"""
    for rule in _BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(rule)

    imp = MagicMock()
    imp.is_from = True
    imp.module = "os"
    imp.names = ["unused_name"]
    imp.line = 1

    mock = MagicMock()
    mock.imports = [imp]
    mock_filepath.write_text("from os import unused_name\n", encoding="utf-8")

    # 只启用 unused-import 规则
    issues = run_semantic_rules(mock, mock_filepath, "python", enabled_rules={"unused-import"})

    assert len(issues) == 1
    assert issues[0].category == "unused-import"


def test_run_semantic_rules_rule_exception_continues(
    mock_filepath: Path,
) -> None:
    """测试单条规则异常不阻断其他规则。"""

    class FailingRule:
        name = "failing"
        languages = {"python"}
        severity = "error"

        def check(self, ast: object, filepath: Path) -> list[Issue]:
            raise RuntimeError("Simulated rule failure")

    class SucceedingRule:
        name = "succeeding"
        languages = {"python"}
        severity = "info"

        def check(self, ast: object, filepath: Path) -> list[Issue]:
            return [
                Issue(
                    file=str(filepath),
                    line=1,
                    column=0,
                    severity="info",
                    category="test",
                    rule_id="test",
                    message="Success",
                )
            ]

    register_semantic_rule(FailingRule())
    register_semantic_rule(SucceedingRule())

    mock = MagicMock()
    issues = run_semantic_rules(mock, mock_filepath, "python")

    # 应该有来自 SucceedingRule 的结果
    assert len(issues) == 1
    assert issues[0].message == "Success"


# ─── Test Builtin Rules Registration ─────────────────────────────────────────


def test_builtin_rules_registered() -> None:
    """测试内置规则已注册。"""
    builtin_names = {rule.name for rule in _BUILTIN_SEMANTIC_RULES}
    assert "unused-import" in builtin_names
    assert "missing-docstring" in builtin_names
    assert "high-complexity" in builtin_names
