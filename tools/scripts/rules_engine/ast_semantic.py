"""AST-based semantic checks that regex rules cannot express.

py-bare-raise 是首个迁移案例: 正则 ``^\\s*raise\\s*$`` 无法判断
raise 是否位于 except 块内, 只能靠 noqa 人工豁免; AST 版本直接
检查 Raise 节点的 exc 属性与祖先 ExceptHandler 链, 语义精确。

## 单入口契约（D-01）

AST 级语义规则此前有**三处直接调用点** (``rules_engine/checker.py``、
``adg_cli/check.py``、``rules_engine/validators/pipeline.py``), 每新增一条
规则都要在多处接线, 职责边界模糊且容易漏接。现统一为:

- 规则实现 :class:`AstSemanticRule` 协议, 注册进 ``_AST_SEMANTIC_RULES``;
- **统一入口** :func:`run_ast_semantic_rules` —— 三条路径都走它;
- :func:`check_python_bare_raise` 保留为兼容包装 (历史 API), 内部同样走
  注册表, 不再自带实现。

新增规则只需注册一次, 三条路径自动生效。
"""

from __future__ import annotations

import ast
from typing import Protocol, runtime_checkable

from .logger import logger
from .models import Issue


@runtime_checkable
class AstSemanticRule(Protocol):
    """AST 语义规则协议: 基于 Python ``ast`` 的单文件检查单元。"""

    name: str
    languages: set[str]
    severity: str = "warning"

    def check(self, filepath: str, lines: list[str]) -> list[Issue]:
        """对单文件执行检查。

        Args:
            filepath: 源文件路径（用于报告定位）。
            lines: 源文件行列表。

        Returns:
            发现的问题列表（空列表表示干净）。
        """
        ...


# 注册表: name -> AstSemanticRule
_AST_SEMANTIC_RULES: dict[str, AstSemanticRule] = {}


def register_ast_semantic_rule(rule: AstSemanticRule) -> None:
    """注册 AST 语义规则（按 name 覆盖同名规则）。"""
    _AST_SEMANTIC_RULES[rule.name] = rule


def unregister_ast_semantic_rule(name: str) -> bool:
    """注销 AST 语义规则，返回是否成功。"""
    return _AST_SEMANTIC_RULES.pop(name, None) is not None


def get_ast_semantic_rules(language: str | None = None) -> list[AstSemanticRule]:
    """列出已注册规则，可按语言过滤。"""
    if language is None:
        return list(_AST_SEMANTIC_RULES.values())
    return [r for r in _AST_SEMANTIC_RULES.values() if language in r.languages]


def list_ast_semantic_rules() -> list[dict[str, object]]:
    """列出所有规则元数据（供 CLI/文档使用）。"""
    return [
        {"name": r.name, "languages": sorted(r.languages), "severity": r.severity} for r in _AST_SEMANTIC_RULES.values()
    ]


def run_ast_semantic_rules(filepath: str, lines: list[str], language: str = "python") -> list[Issue]:
    """**统一入口**: 按语言运行已注册的 AST 语义规则。

    单条规则失败不阻断整体 (与插件系统一致): 规则异常不得让整次检查崩掉;
    但也不得静默吞掉 —— 由 logger 记录 debug 级上下文以便排查。

    Args:
        filepath: 源文件路径。
        lines: 源文件行列表。
        language: 文件语言（决定运行哪些规则）。

    Returns:
        合并的 Issue 列表。
    """
    issues: list[Issue] = []
    for rule in get_ast_semantic_rules(language):
        try:
            issues.extend(rule.check(filepath, lines))
        except Exception:
            logger.debug(f"AST 语义规则 {rule.name} 在 {filepath} 上失败", exc_info=True)
            continue
    return issues


class BareRaiseRule:
    """检测不在 except 处理器内的裸 raise (无法重抛的无效语句)。

    合法场景: Raise 节点出现在某个 ExceptHandler 的 body 中
    (含嵌套 try/except), 此时裸 raise 重抛当前异常。
    非法场景: 函数体/模块级任何非 except 位置的裸 raise,
    运行时会抛 RuntimeError("No active exception to re-raise")。
    """

    name = "py-bare-raise"
    languages = {"python"}
    severity = "error"

    def check(self, filepath: str, lines: list[str]) -> list[Issue]:
        issues: list[Issue] = []
        source = "\n".join(lines)

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return issues  # 语法错误由 py-ast-syntax-error 单独报告

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and node.exc is None and node.cause is None):
                continue
            if _inside_except_handler(node, tree):
                continue
            issues.append(
                Issue(
                    rule_id="py-bare-raise",
                    severity="error",
                    category="error_handling",
                    file=filepath,
                    line=node.lineno,
                    message="Bare raise outside except block",
                    fix_hint="Use 'raise' only inside except blocks, or use 'raise ExceptionType()'",
                )
            )
        return issues


def _inside_except_handler(node: ast.Raise, tree: ast.AST) -> bool:
    """判断 Raise 节点是否位于任一 ExceptHandler 的处理体内。

    ast 没有父节点指针, 采用"位置包含"法: 遍历所有 ExceptHandler,
    若 Raise 的行号落在 handler 体首尾行之间则视为在处理器内。
    对同一行混合多分支的极端情况保守判定为合法 (不误报)。
    """
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        body_nodes = [n for stmt in handler.body for n in ast.walk(stmt)]
        if any(n is node for n in body_nodes):
            return True
    return False


# 注册内置规则
register_ast_semantic_rule(BareRaiseRule())


def check_python_bare_raise(filepath: str, lines: list[str]) -> list[Issue]:
    """兼容包装: 历史 API, 内部走统一注册表 (D-01)。

    只运行 ``py-bare-raise`` 一条规则, 与历史行为完全一致。
    """
    rule = _AST_SEMANTIC_RULES.get("py-bare-raise")
    if rule is None:
        return []
    return rule.check(filepath, lines)
