"""单文件检查实现（checker.check_file 的实现体）。

## 为什么单独成模块

`checker.py` 是目录级编排器, 而 `_checker_workers.py`（进程池 worker）需要
`check_file`。若 `check_file` 留在 `checker.py`, 依赖就成环:

    checker.py → _checker_workers.py → checker.py

环的代价不只是"不好看": 静态依赖图（``arch-cycle`` 守卫）会把它报成
error 级架构问题, 且模块初始化顺序变得脆弱。

把单文件检查下沉到本模块后, 依赖方向单一:

    checker.py        → _checker_file.py
    _checker_workers.py → _checker_file.py

`checker.py` 保留 `check_file` 的重导出, 公开 API 不变。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._checker_linters import _run_external_linters as _run_external_linters
from ._checker_markers import _detect_language as _detect_language
from ._checker_markers import _load_context_markers as _load_context_markers
from ._checker_noqa import _filter_suppressed_issues as _filter_suppressed_issues
from .anti_pattern_checker import check_anti_patterns
from .ast_semantic import run_ast_semantic_rules
from .complexity_checker import check_js_complexity, check_python_complexity
from .context import adjust_severity, detect_file_role
from .logger import logger
from .models import CheckResult, Issue
from .naming_checker import check_naming_conventions
from .plugins import get_plugins_for_language
from .rule_loader import load_rules_for_language


def check_file(
    filepath: Path,
    rules: dict[str, Any] | None = None,
    language: str | None = None,
    semantic: bool = False,
    run_linters: bool = True,
) -> CheckResult:
    """Check a single file against rules.

    Args:
        filepath: Path to the file.
        rules: Rules dict. Auto-loaded if None.
        language: Force language. Auto-detected if None.
        semantic: Enable AST-based semantic analysis (tree-sitter).
        run_linters: Run external linters (ruff/eslint) per file. Disable for
            bulk scans where per-file subprocess spawns dominate runtime.
    """
    skip_result = _check_file_skip_conditions(filepath, language)
    if skip_result:
        return skip_result

    lang, rules, content, lines, skip_issues = _prepare_file_check(filepath, language, rules)
    if lang is None or rules is None or content is None or lines is None:
        return CheckResult(
            file=str(filepath),
            issues=skip_issues,
            language=lang or "unknown",
            skipped=True,
        )

    issues = _run_all_checkers(filepath, content, lines, lang, rules, run_linters=run_linters)
    issues = _filter_suppressed_issues(filepath, issues, lines)
    issues = _apply_context_role(filepath, issues)

    if semantic:
        issues.extend(_run_semantic_checks(filepath, lang))

    return CheckResult(
        file=str(filepath),
        issues=issues,
        language=lang,
    )


def _check_file_skip_conditions(filepath: Path, language: str | None) -> CheckResult | None:
    """检查文件跳过条件, 返回 CheckResult 若应跳过, 否则 None."""
    if not filepath.exists():
        return _file_not_found_result(filepath)

    if filepath.stat().st_size == 0:
        return CheckResult(
            file=str(filepath),
            issues=[],
            language=filepath.suffix.lower().lstrip("."),
            skipped=True,
        )
    return None


def _prepare_file_check(
    filepath: Path, language: str | None, rules: dict[str, Any] | None
) -> tuple[str | None, dict[str, Any] | None, str | None, list[str] | None, list[Issue]]:
    """准备检查所需的语言、规则、内容、行列表, 以及"跳过原因"对应的 issue.

    content/lines 为 None 表示文件无法安全解析 (非UTF-8), 调用方须按 skipped 处理。

    第 5 个通道承载跳过本身的可见记录。skipped 若不携带任何 issue, 门禁无法区分
    "该文件无需检查" 与 "该文件检查失败" —— 后者被呈现为 passed 即 fail-open,
    与 ADR-074/076/078 同一族缺陷。
    """
    lang = language or _detect_language(filepath)
    if lang == "unknown":
        return None, None, "", [], []

    if rules is None:
        rules = load_rules_for_language(lang)

    try:
        # utf-8-sig 而非 utf-8: 后者不剥离 BOM, 导致文件首行的 ^ 锚点规则全部失效。
        content = filepath.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        # 该文件属于受支持语言, 却读不出来 —— 语义上它是"检查失败"而非"无需检查"。
        # 必须留痕, 否则 check_file 返回 skipped=True 且零 issue, 门禁无从察觉。
        logger.warning(f"跳过非 UTF-8 文件 (无法安全解析): {filepath}")
        return lang, rules, None, None, [_undecodable_file_issue(filepath, exc)]

    lines = content.splitlines()
    return lang, rules, content, lines, []


def _apply_context_role(filepath: Path, issues: list[Issue]) -> list[Issue]:
    """应用上下文角色调整严重度."""
    ctx_markers = _load_context_markers(filepath.parent)
    file_role = detect_file_role(filepath, ctx_markers)
    if file_role:
        for issue in issues:
            issue.context_role = file_role
            issue.severity = adjust_severity(issue.severity, file_role)
    return issues


def _undecodable_file_issue(filepath: Path, exc: UnicodeDecodeError) -> Issue:
    """Create the Issue recorded when a supported-language file cannot be decoded."""
    return Issue(
        file=str(filepath),
        line=0,
        column=0,
        severity="error",
        category="io",
        rule_id="file-decode-error",
        message=f"File could not be decoded as UTF-8, so it was not checked: {exc}",
        fix_hint="Re-save the file as UTF-8, or exclude it from the checked paths",
    )


def _file_not_found_result(filepath: Path) -> CheckResult:
    """Create CheckResult for missing file."""
    return CheckResult(
        file=str(filepath),
        issues=[
            Issue(
                file=str(filepath),
                line=0,
                column=0,
                severity="error",
                category="io",
                rule_id="file-not-found",
                message=f"File not found: {filepath}",
            )
        ],
        language=filepath.suffix.lower().lstrip("."),
        skipped=True,
    )


def _run_all_checkers(
    filepath: Path,
    content: str,
    lines: list[str],
    lang: str,
    rules: dict[str, Any],
    run_linters: bool = True,
) -> list[Issue]:
    """Run all checkers on file content."""
    issues: list[Issue] = []

    # Anti-patterns (传入已读的 content/lines, 避免对同一文件重复读盘)
    issues.extend(check_anti_patterns(filepath, lang, rules, content=content, lines=lines))

    # Naming conventions
    issues.extend(check_naming_conventions(lines, rules, str(filepath), lang))

    # Complexity
    if lang == "python":
        issues.extend(check_python_complexity(lines, rules, str(filepath)))
    elif lang in ("javascript", "typescript"):
        issues.extend(check_js_complexity(lines, rules, str(filepath)))

    # AST 语义检查: 正则无法表达的规则 (bare-raise 的 except 块判定)
    # D-01: 统一入口 —— 新增 AST 语义规则只需在 ast_semantic 注册一次,
    # 三条检查路径 (engine / adg_cli / validators) 自动生效。
    issues.extend(run_ast_semantic_rules(str(filepath), lines, lang))

    # Run registered plugins
    for plugin in get_plugins_for_language(lang):
        try:
            issues.extend(plugin.check(filepath, content, lines, lang, rules))
        except Exception:
            # Plugin failed - log at debug level so bugs are visible without
            # breaking the pipeline (CLI 工具 best-effort 模式).
            logger.debug("Plugin {} failed on {}: {}", plugin.__class__.__name__, filepath, exc_info=True)

    # Run external linters
    if run_linters:
        issues.extend(_run_external_linters(filepath, lang))

    return issues


def _run_semantic_checks(filepath: Path, lang: str) -> list[Issue]:
    """Run AST-based semantic analysis on a file.

    Uses tree-sitter for accurate syntax tree analysis instead of regex.
    通过语义规则插件系统执行检查（见 semantic_rules.py），
    新增规则只需注册 SemanticRule，无需修改本模块。

    降级可见性（ADR-064）：tree-sitter 不可用时**不得静默返回空列表**。
    旧实现直接 `return issues`（空），调用方无法区分"检查通过"与
    "检查根本没跑" —— 实测缺失时 SemanticChecker 报 0 个问题，
    而依赖齐全时报 54 个，输出看起来像"代码完美"。现在统一产生一条
    ``semantic-degraded`` error Issue（严重度理由见 _degraded_issue）。
    """
    issues: list[Issue] = []

    try:
        from .ast_parser import get_parser
        from .semantic_rules import run_semantic_rules

        parser = get_parser()
        if not parser.available:
            return [_degraded_issue(filepath, "tree-sitter 未安装")]

        ast_result = parser.parse_file(filepath, lang)
        if ast_result is None:
            # 区分两种 None：解析器缺失 vs 真正解析失败
            # 用公开属性 supported_languages()，不碰私有 _parsers
            if lang not in parser.supported_languages():
                return [_degraded_issue(filepath, f"tree-sitter 的 {lang} 解析器不可用")]
            return [_degraded_issue(filepath, f"{lang} 文件解析失败")]

        # 运行所有匹配语言的语义规则插件
        issues.extend(run_semantic_rules(ast_result, filepath, lang))

    except ImportError as exc:
        return [_degraded_issue(filepath, f"语义检查依赖缺失: {exc}")]
    except Exception as exc:  # noqa: BLE001 - 语义插件异常不中断管道，但降级为可见 Issue
        # 不中断检查管道，但必须留痕（原先 `pass` 会完全静默）
        return [_degraded_issue(filepath, f"语义分析异常: {type(exc).__name__}: {exc}")]

    return issues


def _degraded_issue(filepath: Path, reason: str) -> Issue:
    """语义检查降级时产生的可见 Issue。

    ADR-064: 严重度取 ``error`` 而非 info/warning。实测
    ``CheckResult.passed`` 只看 ``error_count``（models.py:121），实测
    info 与 warning 都会被 report_generator / quality_gate 渲染成
    "PASS ✅" —— 等于把"检查根本没跑"重新伪装成绿灯，正是本 ADR
    要根除的假绿灯。

    取 error 不会误伤常规门禁：全仓仅 ``phase_runner._run_semantic_check``
    以 ``semantic=True`` 调用检查器，且 ``.jcode/hooks.json`` 无任何 hook
    触发 semantic-check（已核验 on_commit/on_pr/on_merge/scheduled）。
    即"显式要求语义检查却没跑成"才会触发 error，属于名副其实的错误。
    """
    return Issue(
        rule_id="semantic-degraded",
        severity="error",
        category="infrastructure",
        file=str(filepath),
        line=0,
        message=f"AST 语义检查未执行: {reason}（本文件的语义规则未被检查）",
        fix_hint="安装可选依赖后重试: uv pip install 'tree-sitter' 'tree-sitter-<lang>'",
        explanation=(
            "语义检查依赖 tree-sitter。缺失时不会报错，但相关规则"
            "（未使用导入、缺 docstring、复杂度等）实际上一条都没跑。"
        ),
    )
