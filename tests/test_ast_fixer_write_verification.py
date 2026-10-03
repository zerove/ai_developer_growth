"""写盘前语法自检兜底回归测试 (ADR-070).

背景 (实测, 非推断):
ADR-069 靠给 ``fix-empty-function`` 加守卫 (跳过同行 ``: ...`` 体)
挡住了破坏代码。该守卫依赖一个**无法验证的假设** —— "每个规则的
守卫都覆盖了所有会产生非法代码的路径"。ADR-070 在**写盘这一层**
加一道与规则无关的兜底: 修复结果只要无法解析就整体回退。

为何必须新增这层 (实测否决了一个想当然的方案):
最初打算直接复用现有 tree-sitter parser 做自检。实测发现
tree-sitter 对 ADR-069 那份被破坏的代码 ``has_error=False`` ——
它**看不见** ``def f(): ...`` 后跟一行 ``pass`` 这种 IndentationError,
而 ``ast.parse`` 能看见。两者在本仓库 681 个 Python 文件上判定
完全一致 (0 分歧), 但恰恰在本缺陷的关键样本上不一致。
故 Python 必须走 ``ast.parse``, 用 tree-sitter 检查 Python 等于没检查。

本文件锁定四件事:
    1. 语法被破坏时**拒绝写盘**, 磁盘内容逐字节不变
    2. 此时 ``applied_fixes`` 必须为 0, 且 CLI 不得输出成功结论
    3. 报告必须给出**可执行的**错误信息 (具体异常类型 + 行号)
    4. 对照组: 合法修复仍正常落盘, 不得被兜底误伤

对照组是必需的 —— 若只断言"文件没被改", 一个"永远拒绝写盘"的
退化实现同样能通过。故本文件同时验证真实修复 (裸 except) 照常生效。
"""

from __future__ import annotations

import ast as python_ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.scripts.rules_engine.ast_fixer import ASTFixer
from tools.scripts.rules_engine.ast_parser import FileAST

REPO_ROOT = Path(__file__).resolve().parent.parent

# 必须带**尾随空行**才可复现 ADR-069 的触发条件 (Phase 45 实测:
# 去掉尾随空行解析器根本不把该函数纳入待修复集合, 缺陷不复现)。
PROTOCOL_ELLIPSIS_SRC = "class P(Protocol):\n    def audit(self) -> bool: ...\n\n"

# 合法修复样本: 裸 except -> except Exception。这是 auto_safe 且修复后
# 语法合法, 用作对照组 —— 兜底绝不能把它也拦下。
BARE_EXCEPT_SRC = '"""M."""\n\n\ndef f():\n    """D."""\n    try:\n        pass\n    except:\n        pass\n'

# 健康代码: 无任何可修复项, 兜底不应介入
CLEAN_SRC = '"""M."""\n\nX = 1\n'


def _run_hook(command: str, path: Path, *, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    """在子进程中运行真实 hooks_runner CLI, 返回 CompletedProcess."""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "scripts" / "hooks_runner.py"),
        command,
        "--path",
        str(path),
        *(extra or []),
    ]
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
        check=False,
    )


# 子进程注入脚本: 让 fix-empty-function 退回 ADR-069 之前的破坏行为。
#
# 为何 CLI 用例必须靠注入而非直接调用: ADR-069 已修, 同行 ``: ...`` 体
# 不再产生修复项, 破坏路径在**正常**的子进程里不可达。若不注入, 用例
# 会看到 "Total fixes found: 0" 并因断言失败 —— 但那是**假失败**,
# 它没有测到兜底, 只是测到守卫还在。这里首次编写时就踩了这个坑:
# CLI 用例报 "汇总未提及语法自检", 而真实原因是驱动根本没触发。
#
# 注入方式是 sitecustomize (只 patch 目标方法, 不改 ast_fixer.py 源文件)
# —— Phase 45 曾因探针直接改真实文件而损坏两个仓库文件, 故此处及
# ``_force_broken_result`` 一律拒绝改写源码。
_INJECT_SITECUSTOMIZE = '''
from pathlib import Path
import re


def _install():
    from tools.scripts.rules_engine.ast_fixer import ASTFixer, FixResult

    def buggy(self, content, ast_result, filepath):
        """ADR-069 修复前的原样实现: 不检查 def 行是否已有同行体."""
        fixes = []
        lines = content.splitlines()
        for func in ast_result.functions:
            if func.body_lines > 1:
                continue
            idx = func.line - 1
            if not (0 <= idx < len(lines)):
                continue
            if idx + 1 < len(lines) and not lines[idx + 1].strip():
                m = re.match(r"^(\\s*)", lines[idx])
                fixes.append(FixResult(
                    rule_id="fix-empty-function",
                    description="Add 'pass' to empty function",
                    file=str(filepath), line=func.line + 1, column=0,
                    original="", replacement=f"{m.group(1) if m else ''}    pass",
                    confidence=0.9, auto_safe=True))
        return fixes

    ASTFixer._fix_empty_functions = buggy


try:
    _install()
except Exception as exc:  # noqa: BLE001
    import sys
    print(f"[sitecustomize] 注入失败: {exc}", file=sys.stderr)
'''


def _run_hook_with_injected_defect(command: str, path: Path) -> subprocess.CompletedProcess[str]:
    """运行真实 CLI, 但注入使破坏路径可达的 sitecustomize.

    全链路 (子进程 -> 修复 -> 写盘 -> 汇总) 均未经简化, 只有
    ``_fix_empty_functions`` 被换回 ADR-069 之前的实现。
    """
    with tempfile.TemporaryDirectory() as inject_dir:
        (Path(inject_dir) / "sitecustomize.py").write_text(_INJECT_SITECUSTOMIZE, encoding="utf-8")
        cmd = [
            sys.executable,
            str(REPO_ROOT / "tools" / "scripts" / "hooks_runner.py"),
            command,
            "--path",
            str(path),
        ]
        return subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
            check=False,
            env={**os.environ, "PYTHONPATH": inject_dir},
        )


class TestBrokenResultIsRejected:
    """核心回归: 会破坏语法的修复结果必须被拒绝写盘.

    本类全部依赖 ``_force_broken_result`` 把 ``fix-empty-function``
    退回 ADR-069 之前的行为 —— 否则该破坏路径不可达, 用例就成了
    空转 (这正是 Phase 45 变异验证翻车的教训)。
    """

    def test_rejecting_write_keeps_file_byte_identical(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """磁盘内容必须逐字节不变."""
        _force_broken_result(monkeypatch)
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=False)

        assert report is not None
        assert src.read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC, "磁盘被修改了"
        python_ast.parse(src.read_text(encoding="utf-8"))  # 仍可解析

    def test_violation_flagged_with_actionable_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """必须标记违规并给出**具体**错误信息.

        断言 "IndentationError" 而非仅 truthy —— CLI 要把这段直接
        透给用户, "出错了" 不足以指导下一步。
        """
        _force_broken_result(monkeypatch)
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=False)

        assert report is not None
        assert report.syntax_violation is True
        assert report.syntax_error is not None
        assert "IndentationError" in report.syntax_error, report.syntax_error

    def test_applied_fixes_must_be_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """applied_fixes 必须归 0 —— 否则又是"报告成功、磁盘未改"."""
        _force_broken_result(monkeypatch)
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=False)

        assert report.applied_fixes == 0, f"报告了 {report.applied_fixes} 项已应用, 但磁盘未变"
        # auto_safe 仍 > 0: 这正是要告诉用户的 —— 本该自动修的没修成。
        assert report.auto_safe_fixes > 0, "该样本本应有 auto_safe 修复, 否则本用例无效"

    def test_fixed_content_falls_back_to_original(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """fixed_content 必须回退为原始内容.

        报告里的 fixed_content 是调用方唯一能拿到的"修复结果"。若它
        仍是被破坏的内容, 任何基于它的下游逻辑都会二次踩坑。
        """
        _force_broken_result(monkeypatch)
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=False)

        assert report.fixed_content == PROTOCOL_ELLIPSIS_SRC
        assert report.fixed_content == report.original_content


class TestCliReportsRejection:
    """真实 CLI 不得输出成功结论.

    两类用例并存:
    - **注入缺陷**的: 验证兜底生效时 CLI 的呈现
    - **不注入**的: 验证守卫仍在时 CLI 的呈现 (对照组)
    """

    def test_cli_never_claims_success_on_rejection(self, tmp_path: Path) -> None:
        """真实子进程: 不打 ✅ Fixes applied, 且 applied 为 0."""
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", src)

        assert proc.returncode == 1, proc.stdout
        assert "✅ Fixes applied" not in proc.stdout, proc.stdout
        assert "Fixes applied: 0" in proc.stdout, proc.stdout
        # 汇总写着 "see messages above" —— 明细里**必须真有**那条消息,
        # 且必须带可执行的具体错误。缺了它, 汇总就是在指向虚空,
        # 用户只知道"被拒"却无从下手。此断言在变异 C 下失败:
        # 删掉明细提示后汇总仍照报, 12 个用例却全绿。
        assert "拒绝写盘" in proc.stdout, f"明细未解释拒绝原因:\n{proc.stdout}"
        assert "IndentationError" in proc.stdout, f"明细缺少具体语法错误:\n{proc.stdout}"
        # 兜底的价值在于文件没坏 —— 必须真的没坏
        assert src.read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC
        python_ast.parse(src.read_text(encoding="utf-8"))

    def test_cli_directory_summary_flags_rejection(self, tmp_path: Path) -> None:
        """目录路径的汇总必须显式呈现被拒文件数."""
        (tmp_path / "p.py").write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", tmp_path)

        # 汇总行的措辞由实现决定, 这里断言"确实提到了 ADR-070"
        # 而不是具体字符串 —— 措辞可改, 语义不可丢。
        assert "ADR-070" in proc.stdout, f"汇总未提及语法自检:\n{proc.stdout}"
        assert "✅ Fixes applied" not in proc.stdout, proc.stdout
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout

    def test_cli_rejection_takes_priority_over_partial_success(self, tmp_path: Path) -> None:
        """部分文件被拒、部分成功时, 汇总仍须报失败.

        这是最容易漏的一档: 一批文件里既有正常修复成功的, 也有
        被兜底拦下的。若按 ``total_applied > 0`` 选结论, 会打印
        ✅ —— 总体上确有未完成的修复, 这仍是假绿灯。
        """
        (tmp_path / "a_broken.py").write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")
        (tmp_path / "b_fine.py").write_text(BARE_EXCEPT_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", tmp_path)

        # 实测值而非推算值: BARE_EXCEPT_SRC 有 2 项发现但只有 1 项
        # auto-safe (fix-empty-except 自 ADR-067 起是 report-only),
        # 而 a_broken.py 被拒后 applied 归 0, 故此处恰为 1。
        # 写成 2 或 "大于 0" 都会把断言与真实行为脱钩。
        assert "Fixes applied: 1" in proc.stdout, f"正常修复未生效:\n{proc.stdout}"
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout
        # 核心: 部分成功也不得报 ✅
        assert "✅ Fixes applied" not in proc.stdout, proc.stdout
        # 且被拒文件确实没坏, 被修文件确实改好了 —— 两者都验
        assert (tmp_path / "a_broken.py").read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC
        assert "except Exception:" in (tmp_path / "b_fine.py").read_text(encoding="utf-8")

    def test_control_cli_reports_clean_file_normally(self, tmp_path: Path) -> None:
        """对照组: 无缺陷时不注入也不该出现任何拒绝提示."""
        src = tmp_path / "clean.py"
        src.write_text(CLEAN_SRC, encoding="utf-8")

        proc = _run_hook("ast-fix", src)

        assert "ADR-070" not in proc.stdout, f"健康文件不该出现语法自检提示:\n{proc.stdout}"
        assert "✅ No fixes needed" in proc.stdout, proc.stdout


class TestControlGroupStillApplies:
    """对照组: 兜底不得误伤合法修复."""

    def test_genuine_fix_still_writes_and_is_verified(self, tmp_path: Path) -> None:
        """裸 except 修复后语法合法, 必须正常落盘且自检标记为"已通过"."""
        src = tmp_path / "bare.py"
        src.write_text(BARE_EXCEPT_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=False)

        assert report is not None
        # is False 而非 falsy: 三态里 None 表示"自检没跑"。若实现
        # 退化成"不调 _verify_syntax", 本断言会失败 —— 这正是它存在的意义。
        assert report.syntax_violation is False, f"自检未运行或结果异常: {report.syntax_violation}"
        assert report.applied_fixes == report.auto_safe_fixes > 0
        assert "except Exception:" in src.read_text(encoding="utf-8")

    def test_clean_file_reports_no_violation(self, tmp_path: Path) -> None:
        """健康文件不得被标记违规.

        内容无变化时自检不跑 (无事可验), 故此处断言 ``is not True``
        而非 ``is False`` —— 两者语义不同, 不可混用。
        """
        src = tmp_path / "clean.py"
        src.write_text(CLEAN_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=False)

        assert report is not None
        assert report.syntax_violation is not True
        assert src.read_text(encoding="utf-8") == CLEAN_SRC

    def test_dry_run_never_triggers_verification(self, tmp_path: Path) -> None:
        """dry-run 不写盘, 不应产生语法违规标记."""
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        report = ASTFixer().fix_file(src, dry_run=True)

        assert report is not None
        assert report.syntax_violation is None
        assert src.read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC


class TestTreeSitterBlindSpot:
    """锁定本 ADR 的实测依据: tree-sitter 看不见 ADR-069 那类破坏.

    这不是给 tree-sitter 挑刺, 而是把"为何 Python 必须用 ast.parse"
    固化为可执行事实。哪天 tree-sitter 修好了, 本用例失败恰好提醒
    可以简化实现。
    """

    def test_tree_sitter_misses_what_ast_parse_catches(self) -> None:
        from tools.scripts.rules_engine.ast_parser import get_parser

        # 必须是**多缩进一层**的 pass。同缩进的 pass 是合法的类体语句,
        # 不是 ADR-069 的破坏形态 —— 首次写本用例时正是踩了这个坑:
        # 样本写成同缩进, ast.parse 通过, 用例反过来报"自检判据失效"。
        # 真实破坏来自 _fix_empty_functions 的替换串 ``f"{indent}    pass"``,
        # 它在 def 的 indent 之上再加 4 空格。
        broken = "class P(Protocol):\n    def audit(self) -> bool: ...\n        pass\n"
        parser = get_parser()
        if "python" not in parser.supported_languages():
            return  # tree-sitter 不可用则本对比无意义

        tree = parser.parse(broken, "python")
        assert tree is not None
        assert tree.root_node.has_error is False, "tree-sitter 已能检出, 可考虑简化 _verify_syntax"

        try:
            python_ast.parse(broken)
        except SyntaxError as exc:
            assert isinstance(exc, IndentationError), f"预期 IndentationError, 实得 {type(exc).__name__}"
        else:
            raise AssertionError("ast.parse 未能检出该破坏, _verify_syntax 的判据失效")


def _force_broken_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """让 ``fix-empty-function`` 退回 ADR-069 之前的破坏行为.

    为何不直接用 ADR-069 的真实缺陷路径: ADR-069 已修复, 同行
    ``: ...`` 体不再产生修复项, 该路径**不可达** (Phase 45 实测确认)。
    故必须先让该路径重新可达, 才能验证兜底 —— 而兜底的价值恰恰
    体现在"守卫漏了"时。

    实现方式为 monkeypatch 掉守卫所在的方法而非改写源码文件:
    Phase 45 曾因探针直接以 ``fix_file(dry_run=False)`` 作用于真实
    文件而损坏两个仓库文件。改写 ``ast_fixer.py`` 同样危险 ——
    测试中途崩溃就会把仓库留在损坏状态。monkeypatch 在用例结束时
    自动还原, 且失败路径也保证还原。
    """
    from tools.scripts.rules_engine.ast_fixer import ASTFixer, FixResult

    def buggy_fix_empty_functions(self: ASTFixer, content: str, ast_result: FileAST, filepath: Path):  # noqa: ANN001, ANN202
        """ADR-069 修复前的原样实现: 不检查 def 行是否已有同行体."""
        fixes: list[FixResult] = []
        lines = content.splitlines()
        for func in ast_result.functions:
            if func.body_lines > 1:
                continue
            func_line_idx = func.line - 1
            if not (0 <= func_line_idx < len(lines)):
                continue
            if func_line_idx + 1 < len(lines) and not lines[func_line_idx + 1].strip():
                indent = re.match(r"^(\s*)", lines[func_line_idx])
                indent_s = indent.group(1) if indent else ""
                fixes.append(
                    FixResult(
                        rule_id="fix-empty-function",
                        description=f"Add 'pass' to empty function '{func.name}'",
                        file=str(filepath),
                        line=func.line + 1,
                        column=0,
                        original="",
                        replacement=f"{indent_s}    pass",
                        confidence=0.9,
                        auto_safe=True,
                    )
                )
        return fixes

    monkeypatch.setattr(ASTFixer, "_fix_empty_functions", buggy_fix_empty_functions)
