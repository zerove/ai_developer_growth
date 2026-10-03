"""ast-fix CLI 谎报 "Fixes applied" 的假绿灯回归测试 (ADR-068).

背景 (实测, 非推断):
ADR-067 把 ``fix-empty-except`` 降级为 ``auto_safe=False`` 后, 跑
``hooks_runner ast-fix --path <探针目录>`` 得到::

      Total fixes: 1
      ✅ Fixes applied

而磁盘上的文件**一个字节都没变**。原因: ``_fix_single_file`` 返回的是
``report.total_fixes``（**发现数**）, ``_print_directory_summary`` 却
依此打印 "Fixes applied"。发现数与应用数在存在 report-only 规则时
本来就可以不同 —— ADR-066 引入 ``applied_fixes`` 正是为了区分它们,
但 CLI 报告层从未采用。

本文件锁定的三件事:
    1. 只有 report-only 规则时, **不得**出现 "✅ Fixes applied"
    2. 混合 auto-safe 与 report-only 时, 应用数必须与磁盘一致
    3. 健康代码库仍打印 "✅ No fixes needed"（真实对照组）

方法论 (沿用 ADR-065 的教训):
用**子进程**跑真实 CLI, 且逐次比对磁盘内容。仅断言函数返回值是不够的 ——
旧实现在那种测试下同样会"通过", 缺陷只体现在 CLI 措辞与磁盘状态上。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EMPTY_EXCEPT_SRC = "try:\n    f()\nexcept Exception:\n    pass\n"
BARE_EXCEPT_SRC = "try:\n    f()\nexcept:\n    print(1)\n"
HEALTHY_SRC = "x = 1\n"


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


def test_report_only_rule_must_not_claim_fixes_applied(tmp_path: Path) -> None:
    """仅 fix-empty-except 时: 报告了但未应用, 不得声称已应用."""
    src = tmp_path / "only.py"
    src.write_text(EMPTY_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", tmp_path)

    assert proc.returncode == 0, proc.stderr
    # 降级后的真实行为: 一个都没应用
    assert "✅ Fixes applied" not in proc.stdout
    assert "review-only" in proc.stdout
    # 但降级不等于隐藏 —— 问题必须仍然被报告出来
    assert "fix-empty-except" in proc.stdout
    # 磁盘必须真的没变
    assert src.read_text(encoding="utf-8") == EMPTY_EXCEPT_SRC


def test_report_only_rule_single_file_path_also_honest(tmp_path: Path) -> None:
    """单文件路径同样不得谎报 —— ADR-066 只修了 verbose, 没修措辞."""
    src = tmp_path / "one.py"
    src.write_text(EMPTY_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", src)

    assert proc.returncode == 0, proc.stderr
    assert "✅ Fixes applied" not in proc.stdout
    assert src.read_text(encoding="utf-8") == EMPTY_EXCEPT_SRC


def test_single_file_exit_code_is_auto_safe_count_not_found(tmp_path: Path) -> None:
    """退出码必须按 auto-safe 数, 不能按发现数或实际应用数.

    ``docs/api/cli.md`` 约定"单文件退出码 = auto-safe 修复数"。
    本 fixture 只有 ``fix-empty-except``（``auto_safe=False``）,
    故三项计数实测为 found=1 / auto_safe=0 / applied=0 —— 三者恰好
    等于"未修改", 因此本用例同时锁住"退出码不来自 applied"。
    """
    src = tmp_path / "one.py"
    src.write_text(EMPTY_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", src)

    assert proc.returncode == 0, proc.stdout
    assert "Total fixes found: 1 (0 auto-safe)" in proc.stdout
    assert "Fixes applied: 0" in proc.stdout


def test_single_file_exit_code_reflects_auto_safe_fixes(tmp_path: Path) -> None:
    """对照组: 存在 auto-safe 修复时, 退出码应等于其数量 (实测 1)."""
    src = tmp_path / "bare.py"
    src.write_text(BARE_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", src)

    # found=1 / auto_safe=1 / applied=1 —— 三数相同, 但分别断言以防
    # 实现退化成只校验其中一个。
    assert "Total fixes found: 1 (1 auto-safe)" in proc.stdout
    assert "Fixes applied: 1" in proc.stdout
    assert proc.returncode == 1, proc.stdout


def test_mixed_rules_applied_count_matches_disk(tmp_path: Path) -> None:
    """混合 auto-safe + report-only: 应用数必须与磁盘改动一致."""
    report_only = tmp_path / "empty.py"
    report_only.write_text(EMPTY_EXCEPT_SRC, encoding="utf-8")
    auto_safe = tmp_path / "bare.py"
    auto_safe.write_text(BARE_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", tmp_path)

    assert proc.returncode == 0, proc.stderr
    # fix-bare-except 语义等价, 应真实落盘
    assert auto_safe.read_text(encoding="utf-8") == "try:\n    f()\nexcept Exception:\n    print(1)\n"
    # fix-empty-except 只报告, 不落盘
    assert report_only.read_text(encoding="utf-8") == EMPTY_EXCEPT_SRC
    # 报告的分子分母必须能对上这两个文件
    assert "Total fixes found: 2" in proc.stdout
    assert "Fixes applied: 1" in proc.stdout


def test_dry_run_never_claims_applied(tmp_path: Path) -> None:
    """dry-run 下一个字节都不该动, 且不得出现已应用字样."""
    src = tmp_path / "bare.py"
    src.write_text(BARE_EXCEPT_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", tmp_path, extra=["--dry-run"])

    assert proc.returncode == 0, proc.stderr
    assert "✅ Fixes applied" not in proc.stdout
    assert src.read_text(encoding="utf-8") == BARE_EXCEPT_SRC


def test_healthy_code_still_reports_no_fixes_needed(tmp_path: Path) -> None:
    """真实对照组: 健康代码库仍应打印 "✅ No fixes needed".

    没有这一条, 上面几个测试即使把汇总结论删成什么都可能"通过"。
    """
    (tmp_path / "ok.py").write_text(HEALTHY_SRC, encoding="utf-8")

    proc = _run_hook("ast-fix", tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "✅ No fixes needed" in proc.stdout
    assert "Total fixes found: 0" in proc.stdout
