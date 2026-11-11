"""D-01 契约: AST 语义规则只有一个入口, 新增规则只需注册一次。

## 背景

AST 级语义规则（正则无法表达的语义判定）此前有**三处直接调用点**:

- ``rules_engine/checker.py::_run_all_checkers``
- ``adg_cli/check.py::_check_ast_semantic``
- ``rules_engine/validators/pipeline.py::validate_file``

每新增一条 AST 规则都要在三处接线, 边界模糊且容易漏接 —— 漏接的后果是
"规则看起来存在, 实际某条路径不生效"（静默少报, fail-open）。

## 契约

- 规则实现 ``AstSemanticRule`` 协议并注册进 ``_AST_SEMANTIC_RULES``;
- **统一入口** ``run_ast_semantic_rules(filepath, lines, language)``;
- ``check_python_bare_raise`` 是兼容包装, 内部同样走注册表, 只跑 bare-raise 一条;
- 三条路径均通过统一入口获取 AST 语义问题;
- 单条规则抛异常不得让整次检查崩掉（也不得静默吞掉）。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.ast_semantic import (
    AstSemanticRule,
    get_ast_semantic_rules,
    list_ast_semantic_rules,
    register_ast_semantic_rule,
    run_ast_semantic_rules,
    unregister_ast_semantic_rule,
)
from tools.scripts.rules_engine.models import Issue

__all__ = [
    "TestBuiltinRegistration",
    "TestEnginePath",
    "TestSingleEntry",
    "TestValidatorPath",
]

_BARE_RAISE_CODE = "def f():\n    raise\n"


class _StubRule:
    """测试用 AST 语义规则。"""

    def __init__(self, name: str, languages: set[str], severity: str = "warning") -> None:
        self.name = name
        self.languages = languages
        self.severity = severity

    def check(self, filepath: str, lines: list[str]) -> list[Issue]:
        return [
            Issue(
                rule_id=self.name,
                severity=self.severity,
                category="stub",
                file=filepath,
                line=1,
                message="stub",
            )
        ]


class TestBuiltinRegistration:
    """内置规则注册与元数据。"""

    def test_bare_raise_is_registered(self) -> None:
        names = {r.name for r in get_ast_semantic_rules()}
        assert "py-bare-raise" in names

    def test_language_filter(self) -> None:
        assert get_ast_semantic_rules("javascript") == []
        assert {r.name for r in get_ast_semantic_rules("python")} == {"py-bare-raise"}

    def test_list_metadata(self) -> None:
        metadata = {m["name"]: m for m in list_ast_semantic_rules()}
        assert metadata["py-bare-raise"]["severity"] == "error"
        assert "python" in metadata["py-bare-raise"]["languages"]


class TestSingleEntry:
    """统一入口的行为。"""

    def test_registered_rule_runs_through_entry(self) -> None:
        rule = _StubRule("stub-rule", {"python"})
        register_ast_semantic_rule(rule)
        try:
            issues = run_ast_semantic_rules("a.py", ["x = 1"], "python")
            assert any(i.rule_id == "stub-rule" for i in issues)
        finally:
            assert unregister_ast_semantic_rule("stub-rule") is True

    def test_unregistered_rule_stops_running(self) -> None:
        rule = _StubRule("stub-rule-2", {"python"})
        register_ast_semantic_rule(rule)
        assert unregister_ast_semantic_rule("stub-rule-2") is True
        issues = run_ast_semantic_rules("a.py", ["x = 1"], "python")
        assert not any(i.rule_id == "stub-rule-2" for i in issues)

    def test_rule_failure_does_not_break_other_rules(self) -> None:
        class _Boom:
            name = "boom-rule"
            languages = {"python"}
            severity = "warning"

            def check(self, filepath: str, lines: list[str]) -> list[Issue]:
                raise RuntimeError("boom")

        register_ast_semantic_rule(_Boom())
        register_ast_semantic_rule(_StubRule("after-boom-rule", {"python"}))
        try:
            issues = run_ast_semantic_rules("a.py", ["x = 1"], "python")
            assert not any(i.rule_id == "boom-rule" for i in issues)
            assert any(i.rule_id == "after-boom-rule" for i in issues), "单条规则失败不得中断后续规则"
        finally:
            unregister_ast_semantic_rule("boom-rule")
            unregister_ast_semantic_rule("after-boom-rule")

    def test_legacy_wrapper_matches_single_rule(self) -> None:
        from tools.scripts.rules_engine.ast_semantic import check_python_bare_raise

        register_ast_semantic_rule(_StubRule("stub-rule-3", {"python"}))
        try:
            legacy = check_python_bare_raise("a.py", _BARE_RAISE_CODE.splitlines())
            entry = run_ast_semantic_rules("a.py", _BARE_RAISE_CODE.splitlines(), "python")
            assert {i.rule_id for i in legacy} == {"py-bare-raise"}
            assert {i.rule_id for i in entry} >= {"py-bare-raise"}
        finally:
            unregister_ast_semantic_rule("stub-rule-3")


class TestEnginePath:
    """rules_engine 路径仍能报出 bare-raise（收敛不得造成静默少报）。"""

    def test_engine_reports_bare_raise(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.checker import check_file

        target = tmp_path / "a.py"
        target.write_text(_BARE_RAISE_CODE, encoding="utf-8")

        result = check_file(target, run_linters=False)

        assert any(i.rule_id == "py-bare-raise" for i in result.issues), "引擎路径不得因收敛而漏报"

    def test_engine_ignores_other_languages(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.checker import check_file

        target = tmp_path / "a.js"
        target.write_text("function f() { throw 1; }\n", encoding="utf-8")

        result = check_file(target, run_linters=False)

        assert not any(i.rule_id == "py-bare-raise" for i in result.issues)


class TestValidatorPath:
    """validators 路径也走统一入口。"""

    def test_validator_reports_bare_raise(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.validators.pipeline import validate_file

        target = tmp_path / "a.py"
        target.write_text(_BARE_RAISE_CODE, encoding="utf-8")

        result = validate_file(target, language="python")

        assert any(i.rule_id == "py-bare-raise" for i in result.issues)


class TestProtocol:
    """协议可运行时判定（注册表接受任何符合协议的规则）。"""

    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(_StubRule("x", {"python"}), AstSemanticRule)

    def test_any_object_satisfies_runtime_protocol(self) -> None:
        class _Anything:
            name = "a"
            languages = {"python"}
            severity = "info"

            def check(self, filepath: str, lines: list[str]) -> list[Issue]:
                return []

        assert isinstance(_Anything(), AstSemanticRule)

    def test_non_rule_object_does_not_satisfy_protocol(self) -> None:
        assert not isinstance(object(), AstSemanticRule)
