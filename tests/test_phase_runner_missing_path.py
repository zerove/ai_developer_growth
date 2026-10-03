"""phase_runner 路径不存在时的假绿灯回归测试 (ADR-065).

背景 (实测):
修复前 ``hooks_runner semantic-check --path <不存在>`` 会让
``check_directory`` 返回空列表, 随后打印 ``✅ ALL CLEAN`` 且 exit 0。
"检查了 0 个文件" 与 "检查通过" 在输出上完全不可分辨 —— 这是
Phase 40 修掉的 checker 降级静默之外的**另一处**同源假绿灯。

本文件锁定三个 phase 函数的同一缺陷:
    semantic-check / ast-fix / hallucination-scan

方法论 (Phase 40 教训):
必须用**子进程**跑真实 CLI, 且必须包含"真实路径仍正常工作"的对照。
只用 ``tmp_path`` 断言函数返回值是不够的 —— 旧实现在这种测试下
同样会"通过", 因为缺陷只在 CLI 的退出码与措辞上体现。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 三个同源 phase 命令: 参数名相同, 行为一致
AFFECTED_COMMANDS = ["semantic-check", "ast-fix", "hallucination-scan"]

# 假绿灯措辞 —— 修复后这些都不应再出现在不存在路径的输出里
FALSE_GREEN_PHRASES = ["ALL CLEAN", "No fixes needed", "No hallucination patterns detected"]


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
        timeout=120,
        cwd=REPO_ROOT,
        check=False,
    )


class TestMissingPathMustFail:
    """路径不存在时必须显式失败, 不得输出假绿灯."""

    def test_missing_dir_exits_nonzero(self, tmp_path: Path) -> None:
        """三个命令在路径不存在时都必须 exit != 0."""
        missing = tmp_path / "definitely-not-here"

        for command in AFFECTED_COMMANDS:
            proc = _run_hook(command, missing)
            assert proc.returncode != 0, f"{command}: 路径不存在却 exit 0 (假绿灯)。输出:\n{proc.stdout}"

    def test_missing_dir_prints_error(self, tmp_path: Path) -> None:
        """必须打印明确的路径错误, 而非静默."""
        missing = tmp_path / "definitely-not-here"

        for command in AFFECTED_COMMANDS:
            proc = _run_hook(command, missing)
            assert "❌ 路径不存在" in proc.stdout, f"{command}: 缺少明确的错误提示。输出:\n{proc.stdout}"

    def test_missing_dir_emits_no_false_green(self, tmp_path: Path) -> None:
        """修复的核心断言: 假绿灯措辞一个都不能出现."""
        missing = tmp_path / "definitely-not-here"

        for command in AFFECTED_COMMANDS:
            proc = _run_hook(command, missing)
            for phrase in FALSE_GREEN_PHRASES:
                assert phrase not in proc.stdout, f"{command}: 修复后仍输出假绿灯 {phrase!r}。输出:\n{proc.stdout}"


class TestExistingPathNotBroken:
    """对照组: 路径存在时行为不能被误伤.

    没有这一组, "无脑 return 1" 也能让上面三个用例全绿。
    """

    def test_clean_file_semantic_check_exits_zero(self, tmp_path: Path) -> None:
        """干净文件必须 exit 0 —— 证明校验不是无脑 return 1.

        探针刻意不含 ``def``, 否则必然命中 ``py-missing-all`` 规则,
        退出码断言会因无关原因失败 (Phase 40 犯过这个错)。
        """
        probe = tmp_path / "clean_probe.py"
        probe.write_text('"""M."""\n\nX = 1\n', encoding="utf-8")

        proc = _run_hook("semantic-check", probe)
        assert proc.returncode == 0, f"干净文件被误判为失败。输出:\n{proc.stdout}"

    def test_clean_dir_ast_fix_exits_zero(self, tmp_path: Path) -> None:
        """无缺陷目录的 ast-fix 必须 exit 0."""
        (tmp_path / "ok.py").write_text('"""M."""\n\nX = 1\n', encoding="utf-8")

        proc = _run_hook("ast-fix", tmp_path, extra=["--dry-run"])
        assert proc.returncode == 0, f"干净目录被误判为失败。输出:\n{proc.stdout}"

    def test_clean_dir_hallucination_scan_exits_zero(self, tmp_path: Path) -> None:
        """无幻觉模式的目录必须 exit 0."""
        (tmp_path / "ok.py").write_text('"""M."""\n\nX = 1\n', encoding="utf-8")

        proc = _run_hook("hallucination-scan", tmp_path)
        assert proc.returncode == 0, f"干净目录被误判为失败。输出:\n{proc.stdout}"
