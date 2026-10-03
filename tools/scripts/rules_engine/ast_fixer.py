"""AST-based safe code transformation engine.

Provides structured code transformations that preserve formatting
and are safe to apply automatically.

Usage:
    from tools.scripts.rules_engine.ast_fixer import ASTFixer

    fixer = ASTFixer()
    result = fixer.fix_file(filepath, rules)
"""

from __future__ import annotations

import ast as python_ast
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.ast_parser import ASTParser, FileAST, get_parser


@dataclass
class FixResult:
    """Result of applying a fix."""

    rule_id: str
    description: str
    file: str
    line: int
    column: int
    original: str
    replacement: str
    confidence: float  # 0.0 to 1.0
    auto_safe: bool  # Safe to apply without review


@dataclass
class FixReport:
    """Summary of all fixes applied to a file."""

    file: str
    fixes: list[FixResult]
    original_content: str
    fixed_content: str
    fix_time_ms: float
    total_fixes: int
    auto_safe_fixes: int
    # ADR-066: 实际改变了内容的修复数。与 total_fixes 区分开, 因为
    # total_fixes 统计的是"发现的可修复项", 不保证每一项都真正改动了文本
    # (例如 _apply_fix 因行号越界而原样返回 —— 该守卫**存在**, 但 Phase 45
    #  全仓 209 文件实测 0 次触发, 属未观测路径)。dry_run 时恒为 0。
    #  已实测的 applied < auto_safe 成因: ADR-067 的 report-only 规则,
    #  以及 ADR-070 的语法自检拒绝写盘。
    applied_fixes: int = 0
    # ADR-070: 修复后内容的语法自检结论, 三态:
    #   True  —— 自检跑了且**失败**, 已拒绝写盘
    #   False —— 自检跑了且通过 (Python 走 ast.parse, 其余走 tree-sitter)
    #   None  —— **自检没跑**(dry_run / 内容无变化 / 校验器不可用)
    # 三态而非两态是必要的: 若"通过"与"没检查"都记 False, 调用方
    # 无法区分"已验证安全"与"根本不知道", 兜底就成了不可观测的。
    syntax_violation: bool | None = None
    # 自检失败的原因 (例如 "IndentationError: ..."), 供 CLI 直接透出。
    syntax_error: str | None = None


class ASTFixer:
    """AST-based code fixer with safety guarantees."""

    def __init__(self) -> None:
        self.parser: ASTParser = get_parser()

    def fix_file(
        self,
        filepath: Path,
        rules: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> FixReport | None:
        """Apply AST-based fixes to a file.

        Args:
            filepath: Path to the file to fix.
            rules: Rules configuration.
            dry_run: If True, only report what would be fixed.

        Returns:
            FixReport with all fixes, or None if parsing fails.
        """
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        language = self.parser._detect_language(filepath)
        tree = self.parser.parse(content, language)
        if tree is None:
            return None

        ast_result = self.parser.parse_file(filepath, language)
        if ast_result is None:
            return None

        start = time.monotonic()
        fixes: list[FixResult] = []

        # Apply various fix strategies
        fixes.extend(self._fix_unused_variables(content, ast_result, filepath))
        fixes.extend(self._fix_bare_except(content, ast_result, filepath))
        fixes.extend(self._fix_bare_except_pass(content, filepath))
        fixes.extend(self._fix_empty_functions(content, ast_result, filepath))
        fixes.extend(self._fix_long_functions(content, ast_result, filepath))

        # Sort fixes by position (reverse order for safe replacement)
        fixes.sort(key=lambda f: (f.line, f.column), reverse=True)

        # Apply fixes
        fixed_content = content
        applied_count = 0
        if not dry_run:
            for fix in fixes:
                if fix.auto_safe:
                    new_content = self._apply_fix(fixed_content, fix)
                    if new_content != fixed_content:
                        applied_count += 1
                    fixed_content = new_content

        # ADR-066: 必须把 fixed_content 写回文件。原实现只算出 fixed_content
        # 却从不落盘, CLI 仍打印 "✅ Fixes applied" 且 exit=total_fixes,
        # 用户以为代码已改而实际未改 —— 属"声称已修复"的假成功。
        # 仅在内容实际变化时写入, 避免无谓的 mtime 变动。
        #
        # ADR-070: 写盘前必须做语法自检。ADR-069 实测证明逐条规则修补
        # 会漏 —— 本规则的守卫能挡住它, 但这依赖"守卫覆盖了所有产生
        # 非法代码的路径"这一假设, 而该假设在 tree-sitter 静默接受非法
        # Python 时无法验证。故在写盘这一层加一道与规则无关的兜底:
        # 修复结果只要无法解析, 就整体回退、不写一个字节。
        syntax_violation: bool | None = None
        syntax_error: str | None = None
        if not dry_run and fixed_content != content:
            checked, violation, error = self._verify_syntax(fixed_content, language)
            # 三态: True=跑了且失败 / False=跑了且通过 / None=跑不了
            # (校验器不可用)。`checked` 与 `violation` 必须分开返回 ——
            # 只靠 `violation is False` 无法区分"已验证安全"与"不知道"。
            syntax_violation = True if violation else (False if checked else None)
            syntax_error = error
            if violation:
                # 拒绝写盘: 报告仍如实返回发现的修复数, 但 applied_fixes
                # 必须归 0 —— 否则又是"报告成功、磁盘未改"的假绿灯。
                fixed_content = content
                applied_count = 0
                syntax_violation = True
                syntax_error = error
        if not dry_run and fixed_content != content:
            try:
                filepath.write_text(fixed_content, encoding="utf-8")
            except OSError:
                # 写回失败必须让调用方知道, 不能静默返回"已修复"报告。
                return None

        fix_time = (time.monotonic() - start) * 1000

        return FixReport(
            file=str(filepath),
            fixes=fixes,
            original_content=content,
            fixed_content=fixed_content,
            fix_time_ms=fix_time,
            total_fixes=len(fixes),
            auto_safe_fixes=sum(1 for f in fixes if f.auto_safe),
            applied_fixes=applied_count,
            syntax_violation=syntax_violation,
            syntax_error=syntax_error,
        )

    def _verify_syntax(self, content: str, language: str) -> tuple[bool, bool, str | None]:
        """校验修复后的内容是否仍可解析 (ADR-070 写盘兜底).

        Returns:
            ``(checked, violation, error)``:
            - ``checked``: 校验器是否可用并真的跑了。
            - ``violation``: 自检跑了且**失败**。
            - ``error``: 失败原因, 供 CLI 透出。

            ``checked=False`` 表示**无法判断**(语言不支持 / 解析器缺失)。
            此时不得谎报"检查通过", 调用方据此把
            ``FixReport.syntax_violation`` 记为 ``None`` 而非 ``False``。

        Python 走 ``ast.parse``, 其余语言走 tree-sitter 的
        ``root_node.has_error``。

        两条路径的灵敏度差异是实测结论, 不能想当然 (ADR-070):
        ``ast.parse`` 拒绝 ``def f(): ...`` 后跟一行多缩进的 ``pass``
        (IndentationError), 而 tree-sitter 对同一份代码
        ``has_error=False`` —— 它**看不见** ADR-069 那类破坏。
        因此 Python 必须用 ``ast.parse``, 用 tree-sitter 检查
        Python 等于没检查。
        """
        if language == "python":
            try:
                python_ast.parse(content)
            except SyntaxError as exc:
                return True, True, f"{type(exc).__name__}: {exc}"
            return True, False, None

        tree = self.parser.parse(content, language)
        if tree is None:
            return False, False, None
        if tree.root_node.has_error:
            return True, True, "tree-sitter reported a syntax error"
        return True, False, None

    def fix_content(
        self,
        content: str,
        language: str,
        rules: dict[str, Any] | None = None,
    ) -> tuple[str, list[FixResult]]:
        """Apply fixes to code content directly.

        Returns:
            Tuple of (fixed_content, list_of_fixes).
        """
        tree = self.parser.parse(content, language)
        if tree is None:
            return content, []

        # Create a temporary FileAST for analysis
        ast_result = FileAST(
            language=language,
            functions=[],
            classes=[],
            imports=[],
            global_variables=[],
            error_nodes=[],
            total_nodes=0,
            parse_time_ms=0,
        )

        fixes: list[FixResult] = []
        fixes.extend(self._fix_bare_except(content, ast_result, Path("<string>")))
        fixes.extend(self._fix_bare_except_pass(content, Path("<string>")))

        fixes.sort(key=lambda f: (f.line, f.column), reverse=True)

        fixed = content
        for fix in fixes:
            if fix.auto_safe:
                fixed = self._apply_fix(fixed, fix)

        return fixed, fixes

    # ─────────────────────────────────────────────────────────────
    # Fix Strategies
    # ─────────────────────────────────────────────────────────────

    def _fix_bare_except(self, content: str, ast_result: FileAST, filepath: Path) -> list[FixResult]:
        """Fix bare except clauses by replacing with except Exception."""
        fixes: list[FixResult] = []
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            match = re.match(r"^(\s*)except\s*:\s*$", line)
            if match:
                indent = match.group(1)
                original = line.rstrip()
                replacement = f"{indent}except Exception:"
                fixes.append(
                    FixResult(
                        rule_id="fix-bare-except",
                        description="Replace bare except with except Exception",
                        file=str(filepath),
                        line=i,
                        column=0,
                        original=original,
                        replacement=replacement,
                        confidence=0.95,
                        auto_safe=True,
                    )
                )

        return fixes

    def _fix_bare_except_pass(self, content: str, filepath: Path) -> list[FixResult]:
        """Fix bare except+pass by adding a comment."""
        fixes: list[FixResult] = []
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            if re.match(r"^\s*except.*:\s*$", line) and i < len(lines):
                next_line = lines[i].strip() if i < len(lines) else ""
                if next_line == "pass":
                    fixes.append(
                        FixResult(
                            rule_id="fix-empty-except",
                            description="Flag silenced exception with a TODO comment",
                            file=str(filepath),
                            line=i + 1,
                            column=0,
                            original="pass",
                            replacement="pass  # TODO: Handle this exception",
                            confidence=0.8,
                            # ADR-067: 原为 auto_safe=True, 但本规则插入的是
                            # # TODO 注释而非真正处理异常 —— 它标记问题而非修复
                            # 问题, 降低代码质量。ADR-066 让 fix_file 真正写盘
                            # 后, 实测 --path tools/scripts --dry-run 有 204 处
                            # auto-safe 修复且抽样全为本规则, 批量注入会污染代码库。
                            # 对比 fix-bare-except (except: -> except Exception:)
                            # 是真正的语义安全改写。二者同标 auto_safe 混淆了
                            # "语法安全"与"质量有益"。降级后仍会被报告, 需人工决定。
                            auto_safe=False,
                        )
                    )

        return fixes

    def _fix_unused_variables(self, content: str, ast_result: FileAST, filepath: Path) -> list[FixResult]:
        """Fix unused variables by prefixing with underscore."""
        fixes: list[FixResult] = []
        lines = content.splitlines()

        # Simple pattern: find "variable = ..." that are never used elsewhere
        # This is a heuristic - full analysis requires cross-referencing
        for i, line in enumerate(lines, 1):
            match = re.match(r"^(\s*)(\w+)\s*=\s*.+$", line)
            if match:
                indent = match.group(1)
                var_name = match.group(2)

                # Skip common patterns
                if var_name.startswith("_") or var_name.isupper():
                    continue
                if var_name in (
                    "self",
                    "cls",
                    "i",
                    "j",
                    "k",
                    "n",
                    "x",
                    "y",
                    "e",
                    "ex",
                    "result",
                    "data",
                    "value",
                ):
                    continue

                # Check if variable is used elsewhere (simple heuristic)
                other_uses = content.count(var_name) - 1  # Subtract the definition
                if other_uses <= 0:
                    fixes.append(
                        FixResult(
                            rule_id="fix-unused-var",
                            description=f"Prefix unused variable '{var_name}' with underscore",
                            file=str(filepath),
                            line=i,
                            column=len(indent),
                            original=var_name,
                            replacement=f"_{var_name}",
                            confidence=0.7,
                            auto_safe=False,  # Requires review
                        )
                    )

        return fixes

    def _fix_empty_functions(self, content: str, ast_result: FileAST, filepath: Path) -> list[FixResult]:
        """Add 'pass' to functions whose body is genuinely absent.

        ADR-069: 原实现只看 def 的**下一行**是否为空, 从不检查 def 行
        自身是否已带 ``: ...`` 这类同行体。实测 ``def f(self) -> bool: ...``
        被判定为"空函数", 修复后变成::

            def f(self) -> bool: ...
                pass

        该文件**无法再被解析** (IndentationError), 而 CLI 同时打印
        ``✅ Fixes applied: 1/1`` —— "报告成功却破坏代码"。

        ``body_lines <= 1`` 涵盖两种本质不同的情形:
        - 体与 def 同行 (``...`` 等): **已有体**, 不可插入
        - 体在下一行且内容为空: **确实无体**, 需要插入

        判据用 ``end_line``: 同行体时 AST 的 ``end_lineno`` 等于
        ``lineno``; 体确实缺失时 ``end_lineno`` 更大（指向空行）。
        这比按文本找冒号可靠 —— ``def f(self, x: int = 3):`` 的
        首个冒号属于参数注解, 文本猜测极易出错。

        实测可达性: Python 不允许空函数体, 因此"确实无体"的输入
        在解析阶段就会失败、根本进不到本规则。基线态全仓扫描
        ``tools/scripts`` 的 209 个文件, ``fix-empty-function``
        **仅有 2 处触发, 且两处都是同行 ``...`` 体** —— 也就是说
        本规则在真实代码库里的唯一实际效果就是**破坏合法代码**。
        修复后触发数归 0, 这是预期结果而非回归。若将来出现真正
        的空体 (如解析器缺陷或非 Python 语言支持), 本规则需重新验证。
        """
        fixes: list[FixResult] = []
        lines = content.splitlines()

        for func in ast_result.functions:
            if func.body_lines > 1:
                continue
            # ADR-069: end_line == line 说明函数体与 def 同行 (``: ...``),
            # 此时已有体, 插入 pass 会直接破坏语法。
            if func.end_line <= func.line:
                continue
            func_line_idx = func.line - 1
            if not (0 <= func_line_idx < len(lines)):
                continue
            func_line = lines[func_line_idx]
            if func_line_idx + 1 < len(lines):
                next_line = lines[func_line_idx + 1].strip()
                if not next_line:
                    if m := re.match(r"^(\s*)", func_line):
                        indent = m.group(1)
                    else:
                        indent = ""
                    fixes.append(
                        FixResult(
                            rule_id="fix-empty-function",
                            description=f"Add 'pass' to empty function '{func.name}'",
                            file=str(filepath),
                            line=func.line + 1,
                            column=0,
                            original="",
                            replacement=f"{indent}    pass",
                            confidence=0.9,
                            auto_safe=True,
                        )
                    )

        return fixes

    def _fix_long_functions(self, content: str, ast_result: FileAST, filepath: Path) -> list[FixResult]:
        """Suggest refactoring for long functions (non-auto)."""
        fixes: list[FixResult] = []

        for func in ast_result.functions:
            if func.body_lines > 50:
                fixes.append(
                    FixResult(
                        rule_id="suggest-refactor",
                        description=f"Function '{func.name}' is {func.body_lines} lines - consider refactoring",
                        file=str(filepath),
                        line=func.line,
                        column=0,
                        original=func.name,
                        replacement="",
                        confidence=0.6,
                        auto_safe=False,
                    )
                )

        return fixes

    # Fix Application
    # ─────────────────────────────────────────────────────────────

    def _apply_fix(self, content: str, fix: FixResult) -> str:
        """Apply a single fix to content."""
        lines = content.splitlines(keepends=True)

        if fix.line < 1 or fix.line > len(lines):
            return content

        line_idx = fix.line - 1
        line = lines[line_idx]

        if fix.original and fix.original in line:
            lines[line_idx] = line.replace(fix.original, fix.replacement, 1)
        elif fix.replacement and not fix.original:
            # Insert new line
            lines.insert(line_idx, fix.replacement + "\n")
        else:
            # Replace entire line
            lines[line_idx] = fix.replacement + "\n"

        return "".join(lines)

    def format_fix_report(self, report: FixReport) -> str:
        """Format a fix report as human-readable text."""
        if not report.fixes:
            return f"No fixes found in {report.file}"

        lines = [
            f"Fix Report: {report.file}",
            "=" * 60,
            f"Total fixes: {report.total_fixes} ({report.auto_safe_fixes} auto-safe)",
            f"Analysis time: {report.fix_time_ms:.1f}ms",
            "",
        ]

        for fix in report.fixes:
            status = "AUTO" if fix.auto_safe else "REVIEW"
            lines.append(f"[{status}] {fix.rule_id} (line {fix.line})")
            lines.append(f"  {fix.description}")
            if fix.original:
                lines.append(f"  - {fix.original}")
            lines.append(f"  + {fix.replacement}")
            lines.append(f"  Confidence: {fix.confidence:.0%}")
            lines.append("")

        return "\n".join(lines)
