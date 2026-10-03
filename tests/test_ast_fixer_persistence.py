"""ASTFixer 落盘与单文件可观测性回归测试 (ADR-066).

两个缺陷, 均为实测确认:

1. **声称已修复却从未落盘**(严重)
   ``ASTFixer.fix_file`` 算出 ``fixed_content`` 后从不写回文件。
   CLI 打印 ``✅ Fixes applied`` 且 ``exit=2``, 而裸 ``except``
   在非 dry-run 运行后依然存在 —— 用户以为代码已改, 实际未改。

2. **单文件路径不显示修复明细**(轻)
   ``_fix_single_file`` 的 ``verbose`` 默认 ``False``, 单文件路径
   未显式开启, 即便真改了文件也只打印标题。

方法论 (Phase 40/41/42 教训):
对照组是必需的 —— 若只断言"文件被修改了", 一个"无脑写回空字符串"
的退化实现同样能通过。故本文件同时锁定:
  - 修复内容正确(裸 except 确实被替换)
  - dry-run 绝不改文件
  - 幂等(已修复文件再跑不重复报告)
  - 干净文件不被误改
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.scripts.rules_engine.ast_fixer import ASTFixer

REPO_ROOT = Path(__file__).resolve().parent.parent

# 含裸 except 的探针 —— 必须确有可修复项, 否则变量根本没被隔离
BARE_EXCEPT_SRC = '"""M."""\n\n\ndef f():\n    """D."""\n    try:\n        pass\n    except:\n        pass\n'

CLEAN_SRC = '"""M."""\n\nX = 1\n'


def _write(path: Path, src: str) -> Path:
    path.write_text(src, encoding="utf-8")
    return path


def _run_cli(command: str, path: Path, *, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
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
        timeout=120,
        cwd=REPO_ROOT,
        check=False,
        env={**os.environ},
    )


class TestFixFileWritesToDisk:
    """核心回归: 报告了修复就必须真的落盘."""

    def test_non_dry_run_actually_modifies_file(self, tmp_path: Path) -> None:
        """非 dry-run 后裸 except 必须从磁盘上消失."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = ASTFixer().fix_file(target, dry_run=False)

        assert report is not None
        on_disk = target.read_text(encoding="utf-8")
        assert "\n    except:" not in on_disk, "裸 except 仍留在磁盘上 —— 修复未落盘"
        assert "except Exception:" in on_disk, "修复内容不正确"

    def test_disk_matches_fixed_content(self, tmp_path: Path) -> None:
        """磁盘内容必须与报告的 fixed_content 一致."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = ASTFixer().fix_file(target, dry_run=False)

        assert report is not None
        assert target.read_text(encoding="utf-8") == report.fixed_content

    def test_applied_fixes_reflects_reality(self, tmp_path: Path) -> None:
        """applied_fixes 必须与 auto_safe_fixes 一致, 不能只报"发现"不报"生效".

        total_fixes 统计的是"发现的可修复项", applied_fixes 统计的是
        "真正改变了文本的项"。两者**本就可以不等**:
        - 非 auto_safe 的项只报告不应用 (ADR-067 降级 fix-empty-except 后,
          本探针的 2 项中有 1 项是 fix-empty-except, 故 2 != 1)
        - _apply_fix 在行号越界时会原样返回内容

        因此正确的不变量是 applied_fixes == auto_safe_fixes, 且
        applied_fixes <= total_fixes。
        """
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = ASTFixer().fix_file(target, dry_run=False)

        assert report is not None
        assert report.applied_fixes == report.auto_safe_fixes, (
            f"applied_fixes={report.applied_fixes} 与 auto_safe_fixes={report.auto_safe_fixes} 不一致"
        )
        assert report.applied_fixes <= report.total_fixes, "实际生效数不应超过发现数"


class TestDryRunNeverWrites:
    """对照组: dry-run 绝不能碰文件."""

    def test_dry_run_leaves_file_untouched(self, tmp_path: Path) -> None:
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)
        before = target.read_text(encoding="utf-8")

        report = ASTFixer().fix_file(target, dry_run=True)

        assert report is not None, "dry-run 也应返回报告"
        assert target.read_text(encoding="utf-8") == before, "dry-run 修改了文件"

    def test_dry_run_reports_zero_applied(self, tmp_path: Path) -> None:
        """dry-run 不实际应用, applied_fixes 必须为 0."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        report = ASTFixer().fix_file(target, dry_run=True)

        assert report is not None
        assert report.applied_fixes == 0
        assert report.total_fixes > 0, "dry-run 仍应发现可修复项"


class TestIdempotentAndClean:
    """对照组: 幂等性与干净文件不被误改."""

    def test_rerun_on_fixed_file_finds_nothing(self, tmp_path: Path) -> None:
        """已修复的文件再跑不应重复应用修复.

        断言口径是 ``applied_fixes == 0`` 而非 ``total_fixes == 0``:
        ``fix-empty-except`` 自 ADR-067 起是 report-only (auto_safe=False),
        它会发现 ``except:`` 已被改成 ``except Exception:`` 之后的 ``pass``
        并继续建议插入 TODO。这是有意为之 —— 降级只影响"是否自动应用",
        不影响"是否被发现"。若断言 total_fixes, 就等于要求把非 auto_safe
        的发现也一并隐藏, 那与分级原则相反。
        """
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)
        ASTFixer().fix_file(target, dry_run=False)

        second = ASTFixer().fix_file(target, dry_run=False)

        assert second is not None
        assert second.applied_fixes == 0, "对已修复文件仍重复应用修复 —— 不幂等"

    def test_clean_file_untouched(self, tmp_path: Path) -> None:
        """无缺陷文件不被改写."""
        target = _write(tmp_path / "clean.py", CLEAN_SRC)
        before = target.read_text(encoding="utf-8")

        report = ASTFixer().fix_file(target, dry_run=False)

        assert report is not None
        assert report.total_fixes == 0
        assert target.read_text(encoding="utf-8") == before


class TestSingleFileCliIsObservable:
    """单文件路径必须显示修复明细."""

    def test_cli_single_file_prints_fix_details(self, tmp_path: Path) -> None:
        """单文件修复时必须打印明细, 而非只有标题.

        注意: "✅ Fixes applied" 只在 ``_print_directory_summary`` 里,
        单文件路径不经过它, 因此不能拿它当断言依据 —— 实测踩过这个坑。
        单文件路径的可见信号是 ``format_fix_report`` 的输出体。
        """
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        proc = _run_cli("ast-fix", target)

        assert "fix-bare-except" in proc.stdout, f"单文件路径未打印修复明细:\n{proc.stdout}"
        assert "Total fixes: 2" in proc.stdout, f"单文件路径未打印修复数量:\n{proc.stdout}"

    def test_cli_single_file_really_changes_file(self, tmp_path: Path) -> None:
        """端到端: CLI 报出修复明细时, 文件必须真的被改过."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        proc = _run_cli("ast-fix", target)

        on_disk = target.read_text(encoding="utf-8")
        assert "fix-bare-except" in proc.stdout, f"预期报告修复明细:\n{proc.stdout}"
        assert "\n    except:" not in on_disk, "CLI 报告已修复但文件未变 —— 假成功"

    def test_cli_dry_run_does_not_change_file(self, tmp_path: Path) -> None:
        """端到端 dry-run: 报告了修复数但磁盘不变."""
        target = _write(tmp_path / "bare.py", BARE_EXCEPT_SRC)

        proc = _run_cli("ast-fix", target, extra=["--dry-run"])

        assert target.read_text(encoding="utf-8") == BARE_EXCEPT_SRC, "dry-run 端到端修改了文件"
        # ADR-068 修正: 退出码按 docs/api/cli.md 的 "auto-safe 修复数"
        # 约定, 本 fixture 实测 2 项发现 / 1 项 auto-safe —— 旧断言
        # 写死 2 (发现数), 恰好等于改对了却仍"看起来正确"。
        # 关键: dry-run 下磁盘未变, 因此退出码绝不能来自 applied。
        assert proc.returncode == 1, f"退出码应为 auto-safe 修复数, 实际 {proc.returncode}"
        assert "Fixes applied: 0" in proc.stdout, "dry-run 不得报告已应用"
