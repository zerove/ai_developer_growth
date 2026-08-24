"""AST-based semantic checks that regex rules cannot express.

py-bare-raise 是首个迁移案例: 正则 ``^\\s*raise\\s*$`` 无法判断
raise 是否位于 except 块内, 只能靠 noqa 人工豁免; AST 版本直接
检查 Raise 节点的 exc 属性与祖先 ExceptHandler 链, 语义精确。
"""

from __future__ import annotations

import ast

from .models import Issue


def check_python_bare_raise(filepath: str, lines: list[str]) -> list[Issue]:
    """检测不在 except 处理器内的裸 raise (无法重抛的无效语句)。

    合法场景: Raise 节点出现在某个 ExceptHandler 的 body 中
    (含嵌套 try/except), 此时裸 raise 重抛当前异常。
    非法场景: 函数体/模块级任何非 except 位置的裸 raise,
    运行时会抛 RuntimeError("No active exception to re-raise")。
    """
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
