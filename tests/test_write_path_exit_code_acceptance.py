"""ADR-071/072 验收测试: 走真实 CLI 观察退出码与磁盘字节。

## 为什么是子进程而不是直接调函数

自动审查指出: 此前对 ADR-071/072 的验证是**间接证据** —— 只跑 pytest 汇总,
没有走用户/CI 实际调用的那条路。本模块全部经 ``subprocess`` 调
``hooks_runner.py``, 与 ``pre-commit`` / CI 的调用方式完全一致,
被观测的是 CLI 自己的退出码与磁盘字节。

## 为什么需要故障注入

拒绝写盘的那条分支, **用真实输入已不可达**: 实测 6 类样本 (裸 except、
空函数、类方法、字符串内 except 等), 没有一类能让 ``auto_safe`` 修复产出
非法 Python —— 逐条规则已逐个修好。不注入则本模块的断言会全部空转。

注入的是**缺陷实现**而非判定结果: ``sitecustomize`` 把
``_fix_empty_functions`` 换成 ADR-069 之前的版本, 于是修复结果**真的是**
非法 Python; 随后观测 CLI 如何反应。这与伪造 ``report.syntax_violation``
字段有本质区别 —— 后者只能验证"代码读了什么字段", 前者验证"代码面对真实
损坏时的行为"。

## 对照组是强制的

每个注入用例都配一个关闭注入的对照组: 同一 CLI、同一输入, 必须正常修复
且退出 0。否则"注入把整个功能打坏"也会让部分断言成立。

变异验证 (实测): 回退 ADR-071 三行 → 恰好 2 条目录用例转红;
短路 ADR-072 写盘兜底 → 恰好 3 条坏正则用例转红; 两者的对照组均保持绿。
"""

import ast
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_RUNNER = REPO_ROOT / "tools" / "scripts" / "hooks_runner.py"

# ── 输入样本 (均为可解析的合法 Python) ──────────────────────────
# 协议方法的单行体 `...` 合法; ADR-069 之前的 buggy 修复器会在其后追加
# pass, 产出 `def audit(self) -> bool: ...    pass` —— 真实非法语法。
BROKEN_SRC = "class P(Protocol):\n    def audit(self) -> bool: ...\n\n"
# 裸 except -> except Exception: auto_safe 且修复后语法合法, 用作对照组。
BARE_EXCEPT_SRC = '"""M."""\n\n\ndef f():\n    """D."""\n    try:\n        pass\n    except:\n        pass\n'
# ADR-072 记录的真实坏正则样本: 规则会把文件改成非法 Python。
BAD_REGEX_SRC = 'import os\ncmd = os.system(f"ls {d()}")\n'
# flag-only 规则样本 (py-star-import): 报告但不自动修。
STAR_IMPORT_SRC = "from os import *\n"
# 合法修复样本 (os.system 无嵌套括号, 正则不会截断)。
VALID_FIX_SRC = "import os\nos.system('ls')\n"

# ADR-069 之前的 buggy _fix_empty_functions: 不检查 def 行是否已有同行体。
_INJECT_SITECUSTOMIZE = """
import os
import sys


def _bootstrap():
    # ADR-079: sitecustomize 由解释器在**启动阶段**执行, 早于任何用户模块
    # 导入, 此时 sys.path[0] 是 hooks_runner.py 所在目录而非仓库根。
    # 少了这段引导, 下面的 `from tools.scripts...` 抛 ModuleNotFoundError,
    # 缺陷没被装上, CLI 走正常路径 → 0 fixes / 退出 0, 用例以"产品缺陷"
    # 的假象变红(与 test_ast_fixer_write_verification.py 同型)。
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


_install()
"""


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:12]


def _parses(p: Path) -> bool:
    try:
        ast.parse(p.read_text())
        return True
    except SyntaxError:
        return False


def run_hook(args: list[str], *, inject_defect: bool = False) -> subprocess.CompletedProcess[str]:
    """跑真实 CLI。inject_defect=True 时用 sitecustomize 注入 buggy 修复器。"""
    env = None
    if inject_defect:
        inject_dir = tempfile.mkdtemp(prefix="adg-inject-")
        Path(inject_dir, "sitecustomize.py").write_text(_INJECT_SITECUSTOMIZE, encoding="utf-8")
        env = os.environ.copy()
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{inject_dir}{':' + prev if prev else ''}"
    try:
        return subprocess.run(
            [sys.executable, str(HOOKS_RUNNER), *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=180,
            env=env,
            check=False,
        )
    finally:
        if env is not None:
            import shutil

            shutil.rmtree(inject_dir, ignore_errors=True)


def ast_fix(path: Path, *, inject_defect: bool = False) -> subprocess.CompletedProcess[str]:
    return run_hook(["ast-fix", "--path", str(path)], inject_defect=inject_defect)


def language_rules(path: Path) -> subprocess.CompletedProcess[str]:
    return run_hook(["language-rules", "--path", str(path), "--fix"])


class TestADRD71DirectoryExitCode:
    """ADR-071: 目录模式存在文件被拒时必须以非零退出。"""

    def test_rejected_file_makes_directory_exit_nonzero(self, tmp_path: Path) -> None:
        """核心需求: 被拒文件的目录必须非零退出, 且磁盘逐字节不变。"""
        target = tmp_path / "a_broken.py"
        target.write_text(BROKEN_SRC, encoding="utf-8")
        before = _md5(target)

        proc = ast_fix(tmp_path, inject_defect=True)

        assert proc.returncode == 1, f"有文件被拒却退出 {proc.returncode}:\n{proc.stdout}"
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout
        assert "✅ Fixes applied" not in proc.stdout, proc.stdout
        assert _md5(target) == before, "被拒文件被改写了"

    def test_partial_success_still_exits_nonzero(self, tmp_path: Path) -> None:
        """部分成功部分被拒时仍非零 —— 最容易漏的一档。

        若实现写成 ``return 0 if total_applied else 1``, 本用例中
        ``total_applied=1`` 会让退出码变 0, 而总体上确有未完成的修复。
        """
        rejected = tmp_path / "a_broken.py"
        rejected.write_text(BROKEN_SRC, encoding="utf-8")
        fine = tmp_path / "b_fine.py"
        fine.write_text(BARE_EXCEPT_SRC, encoding="utf-8")
        b_rej, b_fine = _md5(rejected), _md5(fine)

        proc = ast_fix(tmp_path, inject_defect=True)

        assert proc.returncode == 1, f"部分被拒却退出 {proc.returncode}:\n{proc.stdout}"
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout
        assert _md5(rejected) == b_rej, "被拒文件被改写了"
        assert _md5(fine) != b_fine and _parses(fine), "成功文件未正常修复"

    def test_healthy_directory_still_exits_zero(self, tmp_path: Path) -> None:
        """对照组: 不注入 → 同一输入必须正常处理且退出 0。"""
        (tmp_path / "a_broken.py").write_text(BROKEN_SRC, encoding="utf-8")

        proc = ast_fix(tmp_path, inject_defect=False)

        assert proc.returncode == 0, f"健康目录被误报失败:\n{proc.stdout}"
        assert "❌ Syntax check failed" not in proc.stdout, proc.stdout

    def test_legitimate_fix_still_applies(self, tmp_path: Path) -> None:
        """对照组: 合法修复必须真的生效 —— 防兜底退化成"永不修复"。"""
        target = tmp_path / "b_fine.py"
        target.write_text(BARE_EXCEPT_SRC, encoding="utf-8")
        before = _md5(target)

        proc = ast_fix(tmp_path, inject_defect=True)

        assert proc.returncode == 0, proc.stdout
        assert _md5(target) != before, "合法修复未生效"
        assert _parses(target), "修复后文件无法解析"

    def test_single_file_exit_and_disk_unchanged(self, tmp_path: Path) -> None:
        """单文件路径: 退出码按 auto_safe 项数, 磁盘仍须不变。"""
        target = tmp_path / "a_broken.py"
        target.write_text(BROKEN_SRC, encoding="utf-8")
        before = _md5(target)

        proc = ast_fix(target, inject_defect=True)

        assert proc.returncode != 0, f"被拒却退出 0:\n{proc.stdout}"
        assert "❌ Syntax check failed" in proc.stdout, proc.stdout
        assert _md5(target) == before, "被拒文件被改写了"


class TestADRD72WriteFallback:
    """ADR-072: 写盘前必须校验语法, 且拒绝时不得声称已修复。"""

    def test_bad_regex_rule_refuses_write_and_exits_nonzero(self, tmp_path: Path) -> None:
        """核心需求: 规则会写坏文件 → 拒绝写盘 + 非零退出 + 汇总不谎称成功。"""
        target = tmp_path / "s.py"
        target.write_text(BAD_REGEX_SRC, encoding="utf-8")
        before = _md5(target)

        proc = language_rules(tmp_path)

        assert proc.returncode != 0, f"写盘被拒却退出 0:\n{proc.stdout}"
        assert _md5(target) == before, "被拒文件仍被改写 —— 磁盘已损坏"
        assert "1 auto-fixed" not in proc.stdout, proc.stdout
        assert "manual fixes needed" in proc.stdout, proc.stdout

    def test_flag_only_rule_does_not_redden_exit_code(self, tmp_path: Path) -> None:
        """对照组: flag-only 规则不得让退出码变红, 否则 CI 长期误报。"""
        target = tmp_path / "star.py"
        target.write_text(STAR_IMPORT_SRC, encoding="utf-8")
        before = _md5(target)

        proc = language_rules(tmp_path)

        assert proc.returncode == 0, f"flag-only 规则误伤退出码:\n{proc.stdout}"
        assert _md5(target) == before, "flag-only 规则不应改盘"
        assert "MANUAL FIX REQUIRED" in proc.stdout, proc.stdout

    def test_valid_fix_still_applies(self, tmp_path: Path) -> None:
        """对照组: 合法修复 → 退出 0, 正常改写且仍可解析。"""
        target = tmp_path / "v.py"
        target.write_text(VALID_FIX_SRC, encoding="utf-8")
        before = _md5(target)

        proc = language_rules(tmp_path)

        assert proc.returncode == 0, proc.stdout
        assert _md5(target) != before, "合法修复未生效"
        assert _parses(target), "修复后文件无法解析"
        assert "syntax-check-rejected" not in proc.stdout, proc.stdout


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
