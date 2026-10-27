# 拆分自 tests/test_ast_fixer_write_verification.py

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


PROTOCOL_ELLIPSIS_SRC = "class P(Protocol):\n    def audit(self) -> bool: ...\n\n"


BARE_EXCEPT_SRC = '"""M."""\n\n\ndef f():\n    """D."""\n    try:\n        pass\n    except:\n        pass\n'


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


_INJECT_SITECUSTOMIZE = '''
import os
import sys


def _bootstrap():
    """把仓库根放进 sys.path —— sitecustomize 运行在启动期, 拿不到它。

    判据用"cwd 下存在 tools/scripts/"而非从 __file__ 上溯: sitecustomize 的
    __file__ 指向临时注入目录, 从它上溯毫无意义; 而 cwd 是测试明确设置的
    REPO_ROOT。不满足则说明调用方式变了 —— 必须报错, 不能悄悄退化成
    "注入没装上"。
    """
    root = os.getcwd()
    if not os.path.isdir(os.path.join(root, "tools", "scripts")):
        raise RuntimeError("定位仓库根失败: cwd=%s 下找不到 tools/scripts/" % root)
    if root not in sys.path:
        sys.path.insert(0, root)


_bootstrap()

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


# ADR-079: 不再吞掉异常。注入失败意味着"缺陷没装上", 后续断言必然以
# 产品缺陷的假象失败 —— 那比直接报错更难排查。此处让启动期直接失败,
# 使红灯指向真正的原因。
_install()
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


class TestDirectoryExitCodeOnRejection:
    """目录路径的**退出码**必须反映语法拒绝 (ADR-071).

    为何单独成类: ADR-070 已把"汇总行必须报失败"锁死, 但**退出码**
    无人断言。实测目录路径无条件 ``return 0`` —— 输出打着
    ``❌ Syntax check failed``, 进程却以 0 退出。CI 与 pre-commit
    读的正是退出码, 所以那句 ❌ 等于没说, 仍是一盏假绿灯。

    单文件路径早已按 ``auto_safe`` 项数返回, 目录路径则返回"扫完了";
    本类锁定的是后者在**有文件被拒**时必须非零, 且不得误伤健康的
    目录 (无被拒文件时仍为 0)。
    """

    def test_directory_exit_code_nonzero_when_file_rejected(self, tmp_path: Path) -> None:
        """被拒文件的目录必须以非零退出, 否则 CI 判绿."""
        (tmp_path / "a_broken.py").write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", tmp_path)

        # 核心断言。此前该值为 0 —— 假绿灯的量化表现。
        assert proc.returncode != 0, f"有文件被拒却退出 0:\n{proc.stdout}"
        # 不能只靠退出码: 必须是因语法拒绝而失败, 而不是别的异常。
        # 反向校验 —— 少了这一条, 一个"目录为空所以返回 1"的实现
        # 也能满足上面的非零断言。
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout
        assert (tmp_path / "a_broken.py").read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC

    def test_directory_exit_code_zero_when_nothing_rejected(self, tmp_path: Path) -> None:
        """对照组: 合法修复的目录仍必须退出 0, 修复不能被兜底误伤."""
        (tmp_path / "b_fine.py").write_text(BARE_EXCEPT_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", tmp_path)

        assert proc.returncode == 0, f"健康目录被误报失败:\n{proc.stdout}"
        assert "❌ Syntax check failed" not in proc.stdout, proc.stdout
        assert "Fixes applied: 1" in proc.stdout, f"合法修复未生效:\n{proc.stdout}"
        python_ast.parse((tmp_path / "b_fine.py").read_text(encoding="utf-8"))

    def test_directory_exit_code_nonzero_on_partial_success(self, tmp_path: Path) -> None:
        """部分成功部分被拒时仍非零 —— 最容易漏的一档.

        若实现写成 ``return 0 if total_applied else 1``, 本用例中的
        ``total_applied=1`` 会让退出码变 0, 而总体上确有未完成的修复。
        """
        (tmp_path / "a_broken.py").write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")
        (tmp_path / "b_fine.py").write_text(BARE_EXCEPT_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", tmp_path)

        assert proc.returncode != 0, f"部分被拒却退出 0:\n{proc.stdout}"
        assert "Fixes applied: 1" in proc.stdout, f"正常修复未生效:\n{proc.stdout}"
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout
        assert (tmp_path / "a_broken.py").read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC
        python_ast.parse((tmp_path / "b_fine.py").read_text(encoding="utf-8"))

    def test_single_file_exit_code_still_follows_auto_safe_convention(self, tmp_path: Path) -> None:
        """单文件路径的退出码约定不得被本次修复改动.

        单文件返回的是 ``auto_safe`` 项数(与通过/失败无关), 这是
        ``docs/api/cli.md`` 写明的既有契约。本次只叠加"目录被拒则非零",
        绝不能顺手把单文件也改成 0/1 —— 那会让既有 CI 阈值全部失准。
        实测被拒的单文件: auto_safe=1 且被拒, 故退出码仍是 1。
        """
        src = tmp_path / "p.py"
        src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

        proc = _run_hook_with_injected_defect("ast-fix", src)

        # auto_safe 项数为 1, 无论是否被拒 —— 契约是"项数", 不是"成败"。
        assert proc.returncode == 1, proc.stdout
        assert src.read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC
