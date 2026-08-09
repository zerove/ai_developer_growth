"""语义规则插件系统（AST 级分析）。

扩展点：新增 AST 级检查无需修改核心 check_file 逻辑，
只需注册一个 SemanticRule 实现。

用法:
    from tools.scripts.rules_engine.semantic_rules import SemanticRule, register_semantic_rule

    class RequiresDocstringRule(SemanticRule):
        name = "requires-docstring"
        languages = {"python", "rust"}
        severity = "info"

        def check(self, ast_result, filepath):
            issues = []
            for func in ast_result.functions:
                if not func.name.startswith("_") and func.docstring is None:
                    issues.append(...)
            return issues

    register_semantic_rule(RequiresDocstringRule())
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .models import Issue

if TYPE_CHECKING:
    pass


@runtime_checkable
class SemanticRule(Protocol):
    """语义规则协议：基于 AST 的跨文件检查单元。"""

    name: str
    languages: set[str]
    severity: str = "warning"

    def check(self, ast: object, filepath: Path) -> list[Issue]:
        """对单文件 AST 执行检查。

        Args:
            ast: FileAST 解析结果。
            filepath: 源文件路径（用于报告定位）。

        Returns:
            发现的问题列表（空列表表示干净）。
        """
        ...


# 注册表：name -> SemanticRule
_SEMANTIC_RULES: dict[str, SemanticRule] = {}


def register_semantic_rule(rule: SemanticRule) -> None:
    """注册一个语义规则（按 name 覆盖同名规则）。"""
    _SEMANTIC_RULES[rule.name] = rule


def unregister_semantic_rule(name: str) -> bool:
    """注销语义规则，返回是否成功。"""
    return _SEMANTIC_RULES.pop(name, None) is not None


def get_semantic_rules(language: str | None = None) -> list[SemanticRule]:
    """列出已注册规则，可按语言过滤。

    Args:
        language: 语言名（None = 全部规则）。

    Returns:
        匹配的规则列表。
    """
    if language is None:
        return list(_SEMANTIC_RULES.values())
    return [r for r in _SEMANTIC_RULES.values() if language in r.languages]


def list_semantic_rules() -> list[dict[str, object]]:
    """列出所有规则元数据（供 CLI/文档使用）。"""
    return [
        {"name": r.name, "languages": sorted(r.languages), "severity": r.severity} for r in _SEMANTIC_RULES.values()
    ]


def clear_semantic_rules() -> None:
    """清空全部语义规则（测试/热重载使用）。"""
    _SEMANTIC_RULES.clear()


# ─────────────────────────────────────────────────────────────
# 内置语义规则（与 checker.py 中原有逻辑对齐）
# ─────────────────────────────────────────────────────────────


class _BaseSemanticRule:
    """语义规则基类：提供通用字段默认值（普通类，子类可覆盖类属性）。"""

    name: str = ""
    languages: set[str] = set()
    severity: str = "warning"

    def check(self, file: object, filepath: Path) -> list[Issue]:
        """默认实现：无检查逻辑（子类必须覆盖）。"""
        return []


class UnusedImportRule(_BaseSemanticRule):
    """检测未使用导入（启发式：全文出现次数 <= 1）。"""

    name = "unused-import"
    languages = {"python", "javascript", "typescript"}
    severity = "warning"

    def check(self, file: object, filepath: Path) -> list[Issue]:
        issues: list[Issue] = []
        ast_obj = getattr(file, "imports", None)
        if ast_obj is None:
            return issues
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            return issues

        for imp in ast_obj:
            if not getattr(imp, "is_from", False):
                continue
            for name in getattr(imp, "names", []) or []:
                if name == "*":
                    continue
                # 出现次数 <= 1 说明只有导入语句本身引用
                if content.count(name) <= 1:
                    issues.append(
                        Issue(
                            file=str(filepath),
                            line=getattr(imp, "line", 1),
                            column=0,
                            severity=self.severity,
                            category="unused-import",
                            rule_id="semantic-unused-import",
                            message=f"Import '{name}' from '{getattr(imp, 'module', '')}' appears unused",
                        )
                    )
        return issues


class MissingDocstringRule(_BaseSemanticRule):
    """检测公开函数缺少 docstring。"""

    name = "missing-docstring"
    languages = {"python"}
    severity = "info"

    def check(self, file: object, filepath: Path) -> list[Issue]:
        issues: list[Issue] = []
        functions = getattr(file, "functions", None)
        if functions is None:
            return issues
        for func in functions:
            name = getattr(func, "name", "")
            if name.startswith("_"):
                continue
            if getattr(func, "docstring", None) is None:
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=getattr(func, "line", 1),
                        column=0,
                        severity=self.severity,
                        category="missing-docstring",
                        rule_id="semantic-missing-docstring",
                        message=f"Public function '{name}' lacks a docstring",
                    )
                )
        return issues


class HighComplexityRule(_BaseSemanticRule):
    """检测高圈复杂度函数（> 10）。"""

    name = "high-complexity"
    languages = {"python", "javascript", "typescript", "rust", "go"}
    severity = "warning"

    def check(self, file: object, filepath: Path) -> list[Issue]:
        issues: list[Issue] = []
        functions = getattr(file, "functions", None)
        if functions is None:
            return issues
        for func in functions:
            complexity = getattr(func, "complexity", 1) or 1
            if complexity > 10:
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=getattr(func, "line", 1),
                        column=0,
                        severity=self.severity,
                        category="complexity",
                        rule_id="semantic-high-complexity",
                        message=(
                            f"Function '{getattr(func, 'name', '')}' has AST-estimated complexity {complexity} (>10)"
                        ),
                    )
                )
        return issues


# 注册内置规则
_BUILTIN_SEMANTIC_RULES: list[_BaseSemanticRule] = [
    UnusedImportRule(),
    MissingDocstringRule(),
    HighComplexityRule(),
]
for _rule in _BUILTIN_SEMANTIC_RULES:
    register_semantic_rule(_rule)


def run_semantic_rules(
    file: object,
    filepath: Path,
    language: str,
    enabled_rules: set[str] | None = None,
) -> list[Issue]:
    """对单文件运行所有匹配语言的语义规则。

    Args:
        file: FileAST 解析结果。
        filepath: 源文件路径。
        language: 文件语言。
        enabled_rules: 仅运行指定规则名集合（None = 全部）。

    Returns:
        合并的 Issue 列表。
    """
    issues: list[Issue] = []
    for rule in get_semantic_rules(language):
        if enabled_rules is not None and rule.name not in enabled_rules:
            continue
        try:
            issues.extend(rule.check(file, filepath))
        except Exception:
            # 单条规则失败不阻断整体
            continue
    return issues
