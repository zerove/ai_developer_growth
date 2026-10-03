"""auto-fix 写盘前语法自检回归测试 (ADR-072).

背景 (真实 CLI 实测, **无需注入任何缺陷**):

``tools/scripts/rules_engine/auto_fix.py`` 的 ``py-os-system`` 等规则
使用 ``[^)]+`` 捕获组, 遇到嵌套括号就在第一个 ``)`` 处截断::

    os.system(get_cmd())  ->  subprocess.run(get_cmd(, shell=True, check=True))

修复前 ``language-rules --fix`` 对此打印 ``1 auto-fixed``、退出 0,
并把无法解析的文件留在磁盘上。这比 ADR-070 那处更糟: 汇总**明确
声称修复成功**, 而文件已经坏了。

本文件锁定:
    1. 修复结果无法解析时**拒绝写盘**, 磁盘逐字节不变
    2. 拒绝时汇总不得出现 "auto-fixed", 且 CLI 退出非零
    3. flag-only 规则的 MANUAL FIX REQUIRED **不得**弄红退出码
    4. 对照组: 合法修复照常落盘 (兜底不能变成"永不修复")

第 4 条是必需的 —— 一个"永远拒绝写盘"的退化实现同样能通过 1-3。
"""

from __future__ import annotations

import ast as python_ast
import subprocess
import sys
from pathlib import Path

import pytest

from tools.scripts.rules_engine.auto_fix import apply_fixes, apply_fixes_to_directory

REPO_ROOT = Path(__file__).resolve().parent.parent

# 真实破坏样本: 合法 Python, 但 py-os-system 会把它改成非法 Python。
# 不需要任何 monkeypatch —— 缺陷就在 fixes 规则本身。
BROKEN_BY_REGEX_SRC = "import os\ncmd = os.system(get_cmd())\n"

# 健康对照: 同一规则也能正常修复的合法样本。
HEALTHY_SRC = "import os\ncmd = os.system('ls')\n"

# flag-only 规则产物: MANUAL FIX REQUIRED 属正常, 退出码必须仍为 0。
FLAG_ONLY_SRC = "from os import *\nx = 1\n"


class TestRegexFixRejectedOnSyntaxError:
    """库层: 语法被破坏时必须拒绝写盘."""

    def test_file_left_byte_identical(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text(BROKEN_BY_REGEX_SRC, encoding="utf-8")

        apply_fixes(target, language="python")

        assert target.read_text(encoding="utf-8") == BROKEN_BY_REGEX_SRC, "磁盘被改坏了"

    def test_result_reports_rejection_not_success(self, tmp_path: Path) -> None:
        """返回结果必须如实说明被拒, 且不得计入 auto-fixed."""
        target = tmp_path / "s.py"
        target.write_text(BROKEN_BY_REGEX_SRC, encoding="utf-8")

        results = apply_fixes(target, language="python")

        assert results, "被拒写盘却返回空结果, 调用方无从得知"
        assert all(r.rule_id == "syntax-check-rejected" for r in results), [r.rule_id for r in results]
        # 关键: 这些结果不得被 _summarize 算成 auto_fixed
        assert all(r.fixed == "[MANUAL FIX REQUIRED]" for r in results), [r.fixed for r in results]

    def test_control_healthy_file_still_fixed(self, tmp_path: Path) -> None:
        """对照组: 合法样本必须照常修复 —— 兜底不得变成永不修复."""
        target = tmp_path / "ok.py"
        target.write_text(HEALTHY_SRC, encoding="utf-8")

        results = apply_fixes(target, language="python")

        after = target.read_text(encoding="utf-8")
        assert "subprocess.run" in after, f"合法修复未生效:\n{after}"
        python_ast.parse(after)
        assert all(r.rule_id != "syntax-check-rejected" for r in results)

    def test_dry_run_never_writes(self, tmp_path: Path) -> None:
        """dry_run 必须保持原样, 且不触发拒绝记录."""
        target = tmp_path / "s.py"
        target.write_text(BROKEN_BY_REGEX_SRC, encoding="utf-8")

        apply_fixes(target, language="python", dry_run=True)

        assert target.read_text(encoding="utf-8") == BROKEN_BY_REGEX_SRC


class TestDirectoryMode:
    """目录扫描同样不得写坏文件."""

    def test_directory_leaves_broken_files_untouched(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text(BROKEN_BY_REGEX_SRC, encoding="utf-8")
        (tmp_path / "b.py").write_text(BROKEN_BY_REGEX_SRC, encoding="utf-8")

        apply_fixes_to_directory(tmp_path, dry_run=False, languages=["python"])

        for name in ("a.py", "b.py"):
            assert (tmp_path / name).read_text(encoding="utf-8") == BROKEN_BY_REGEX_SRC


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(REPO_ROOT / "tools" / "scripts" / "hooks_runner.py"), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
        check=False,
    )


class TestRealCLI:
    """真实子进程: CLI 的呈现与退出码."""

    def test_cli_exit_nonzero_and_no_auto_fixed_claim(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text(BROKEN_BY_REGEX_SRC, encoding="utf-8")

        proc = _run_cli("language-rules", "--path", str(tmp_path), "--fix")

        assert target.read_text(encoding="utf-8") == BROKEN_BY_REGEX_SRC
        assert "auto-fixed" in proc.stdout, proc.stdout
        # 汇总必须显示 0 项已修复。此前是 "1 auto-fixed"。
        assert "0 auto-fixed" in proc.stdout, f"仍在声称修复成功:\n{proc.stdout}"
        assert "拒绝写盘" in proc.stdout, f"未说明拒绝原因:\n{proc.stdout}"
        # 核心: 机器读的那一个信号
        assert proc.returncode != 0, f"被拒写盘却退出 0:\n{proc.stdout}"

    def test_cli_flag_only_still_exits_zero(self, tmp_path: Path) -> None:
        """对照组: flag-only 的 MANUAL FIX REQUIRED 不得弄红退出码.

        这是最容易被"顺手一起改坏"的一档。若把退出码改成
        "有 MANUAL FIX REQUIRED 就非零", 既有 CI 会长期红 ——
        flag-only 规则(如 py-star-import)本就以该标记为正常产物。
        """
        target = tmp_path / "star.py"
        target.write_text(FLAG_ONLY_SRC, encoding="utf-8")

        proc = _run_cli("language-rules", "--path", str(tmp_path), "--fix")

        assert "MANUAL FIX REQUIRED" in proc.stdout, proc.stdout
        assert proc.returncode == 0, f"flag-only 被误判为失败:\n{proc.stdout}"

    def test_cli_control_healthy_fix_exits_zero(self, tmp_path: Path) -> None:
        """对照组: 合法修复仍落盘且退出 0."""
        target = tmp_path / "ok.py"
        target.write_text(HEALTHY_SRC, encoding="utf-8")

        proc = _run_cli("language-rules", "--path", str(tmp_path), "--fix")

        assert "subprocess.run" in target.read_text(encoding="utf-8")
        python_ast.parse(target.read_text(encoding="utf-8"))
        assert proc.returncode == 0, proc.stdout
        assert "1 auto-fixed" in proc.stdout, proc.stdout


class TestWriteFailureSurfaced:
    """写盘失败必须让调用方知道, 不能静默返回成功."""

    def test_oserror_is_reported(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """模拟 write_text 抛 OSError, 验证不再静默吞掉.

        修复前 ``_write_if_changed`` 直接 write_text, OSError 会向上
        冒泡; 但若将来有人给它加 try/except 吞掉, 就会退回"报告成功、
        磁盘未改"。本用例锁住"写失败必须成为一条结果"。
        """
        target = tmp_path / "ok.py"
        target.write_text(HEALTHY_SRC, encoding="utf-8")

        def boom(*args: object, **kwargs: object) -> None:
            raise OSError("disk full (simulated)")

        monkeypatch.setattr(Path, "write_text", boom)

        results = apply_fixes(target, language="python")

        assert [r.rule_id for r in results] == ["write-failed"]
        assert all(r.fixed == "[MANUAL FIX REQUIRED]" for r in results)
