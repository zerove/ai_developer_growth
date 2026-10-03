"""fix-empty-function 破坏语法的假绿灯回归测试 (ADR-069).

背景 (实测, 非推断):
``ast-fix`` 对协议类的 ``: ...`` 同行函数体插入 ``pass``, 产出::

    class P(Protocol):
        def audit(self) -> bool: ...
            pass

该文件**无法再被解析** (IndentationError), 而 CLI 同时打印::

    Total fixes found: 1 (1 auto-safe)
    Fixes applied: 1
    ✅ Fixes applied: 1/1

这比 ADR-064~068 的假绿灯更严重: 前五处是**报告与真实状态脱节**,
本处是**报告成功却实际破坏了代码**。而本仓库自身就有两处
``Protocol`` 方法命中该形态, 意味着任何一次非 dry-run 的
``ast-fix`` 都会直接损坏 ``domain_checks.py`` 与 ``contract.py``。

本文件锁定三件事:
    1. ``: ...`` 同行体**不得**被插入 pass, 磁盘保持原样
    2. 修复后的文件必须仍能被 ``ast.parse`` 解析
    3. 修复后 ``ast-fix`` 必须显示 ``Total fixes found: 0``

方法论:
端到端跑真实 ``hooks_runner`` CLI, 并对磁盘内容做 ``ast.parse``。
只断言 ``FixReport`` 字段不够 —— 缺陷的后果是**文件不可解析**,
只有真正 parse 过磁盘内容才能观测到。
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 必须带**尾随空行**才可复现。实测: 去掉尾随空行后, 解析器根本不把
# 该函数纳入待修复集合 (found=0), 缺陷不复现 —— 触发条件比
# "同行体"更窄, 这一点在写测试时才发现。
PROTOCOL_ELLIPSIS_SRC = "class P(Protocol):\n    def audit(self) -> bool: ...\n\n"
BARE_EXCEPT_SRC = "try:\n    f()\nexcept:\n    print(1)\n"


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


def test_inline_ellipsis_body_must_not_be_modified(tmp_path: Path) -> None:
    """`: ...` 同行体已有体, 插入 pass 会破坏语法 —— 必须保持原样."""
    src = tmp_path / "p.py"
    src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", src)

    assert proc.returncode == 0, proc.stderr
    assert src.read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC, "同行体被错误地插入了 pass"
    assert "fix-empty-function" not in proc.stdout, f"不应报告该修复:\n{proc.stdout}"
    assert "Total fixes found: 0" in proc.stdout


def test_result_must_remain_parseable(tmp_path: Path) -> None:
    """核心断言: 修复后的磁盘内容必须仍可被 ast.parse 解析.

    没有这一条, 上一个用例即使退化成"不修改文件但仍声称已修复"
    也可能蒙混过关 —— 真正观测后果的是**解析磁盘内容**。
    """
    src = tmp_path / "p.py"
    src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

    _run_hook("ast-fix", src)

    content = src.read_text(encoding="utf-8")
    # ast.parse 成功即通过; SyntaxError 会让本用例直接失败,
    # 且 pytest 会打印出错位置与内容, 便于定位。
    ast.parse(content)


def test_dry_run_reports_nothing_for_inline_body(tmp_path: Path) -> None:
    """dry-run 也必须显示 0 —— 缺陷在 dry-run 下同样可见, 只是不落盘."""
    src = tmp_path / "p.py"
    src.write_text(PROTOCOL_ELLIPSIS_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", src, extra=["--dry-run"])

    assert "Total fixes found: 0" in proc.stdout, proc.stdout
    assert src.read_text(encoding="utf-8") == PROTOCOL_ELLIPSIS_SRC


def test_mixed_file_only_applies_genuinely_safe_fix(tmp_path: Path) -> None:
    """混合场景: 协议方法不动, 裸 except 仍正常修复, 且整体可解析."""
    src = tmp_path / "mix.py"
    src.write_text(PROTOCOL_ELLIPSIS_SRC + "\n\n" + BARE_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", src)

    content = src.read_text(encoding="utf-8")
    ast.parse(content)  # 修复后必须仍可解析
    assert "def audit(self) -> bool: ..." in content, "协议方法被破坏"
    assert "    pass\n" not in content.split(BARE_EXCEPT_SRC)[0], "协议方法被插入了 pass"
    assert "except Exception:" in content, "真正的 auto-safe 修复未生效"
    assert "Total fixes found: 1" in proc.stdout, proc.stdout
    assert "Fixes applied: 1" in proc.stdout


def test_repository_protocol_files_stay_intact(tmp_path: Path) -> None:
    """真实对照: 仓库内两处 Protocol 方法不得被 ast-fix 改动.

    这两条是真会被损坏的文件 (`domain_checks.py` /
    `parsers/contract.py`), 用真实内容守住比构造用例更有意义。
    """
    real = REPO_ROOT / "tools" / "scripts" / "rules_engine" / "parsers" / "contract.py"
    probe = tmp_path / "contract.py"
    probe.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    before = probe.read_text(encoding="utf-8")

    proc = _run_hook("ast-fix", probe)

    after = probe.read_text(encoding="utf-8")
    assert after == before, "仓库内 Protocol 方法被 ast-fix 改动了"
    ast.parse(after)
    assert "fix-empty-function" not in proc.stdout, proc.stdout
