"""增量测试 fail-closed 行为单元测试。

验证：
- 空变更集 → 跳过（不回退全量）
- git 比较失败（返回码非 0）→ 回退全量（fail-closed）
- base 不可解析（rev-parse 失败）→ 回退全量（fail-closed）
- 正常变更集 → 生成正确的增量 pytest 命令
- ADG_TEST_RERUNS 环境变量优先于配置
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.hooks import basic_checks


def test_empty_changed_python_files_skips() -> None:
    """空变更集：应跳过增量测试，不触发全量回退。"""
    with (
        patch.object(basic_checks, "_changed_python_files", return_value=([], True)),
        patch.object(basic_checks, "run_tests", return_value=(True, "full")) as mock_full,
    ):
        ok, msg = basic_checks.run_tests_incremental(base="HEAD")
        assert ok is True
        assert "skipped" in msg
        mock_full.assert_not_called()


def test_git_diff_failure_falls_back_to_full() -> None:
    """git diff 失败（ok=False）：必须回退全量（fail-closed）。"""
    with (
        patch.object(basic_checks, "_changed_python_files", return_value=([], False)),
        patch.object(basic_checks, "run_tests", return_value=(False, "full-run")) as mock_full,
    ):
        ok, msg = basic_checks.run_tests_incremental(base="HEAD")
        assert ok is False
        assert "full-run" in msg
        mock_full.assert_called_once()


def test_unresolvable_base_falls_back_to_full() -> None:
    """base 不可解析：rev-parse 失败时回退全量（fail-closed）。"""

    def fake_run(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        if cmd and cmd[:3] == ["git", "rev-parse", "--verify"]:
            raise subprocess.CalledProcessError(1, cmd)
        return MagicMock(returncode=0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(basic_checks, "run_tests", return_value=(True, "full")) as mock_full,
    ):
        ok, msg = basic_checks.run_tests_incremental(base="nonexistent-ref")
        assert ok is True
        assert "full" in msg
        mock_full.assert_called_once()


def test_normal_changed_set_builds_incremental_command() -> None:
    """正常变更集：应构造包含目标测试文件的增量 pytest 命令。"""
    changed = [Path("tools/scripts/hooks/basic_checks.py")]
    targets = [Path("tests/test_basic_checks.py")]

    with (
        patch.object(basic_checks, "_changed_python_files", return_value=(changed, True)),
        patch.object(basic_checks, "_tests_for_modules", return_value=targets),
        patch.object(basic_checks, "_plugin_available", return_value=False),
        patch.object(basic_checks, "_setting", return_value="auto"),
        patch.object(basic_checks, "_get_test_reruns", return_value=0),
        patch.object(basic_checks, "_get_timeout", return_value=300),
        patch.object(basic_checks, "_run_subprocess") as mock_run,
    ):
        mock_run.return_value = (True, "ok")
        ok, summary = basic_checks.run_tests_incremental(base="HEAD")
        assert ok is True
        assert "Incremental scope" in summary
        args, kwargs = mock_run.call_args
        cmd = args[0]
        # 验证命令包含 pytest 解释器调用
        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "pytest" in cmd
        assert str(targets[0]) in cmd


def test_adg_test_reruns_env_override_respected() -> None:
    """ADG_TEST_RERUNS 环境变量应优先于配置。"""
    changed = [Path("tools/scripts/hooks/basic_checks.py")]
    targets = [Path("tests/test_basic_checks.py")]

    with (
        patch.dict(os.environ, {"ADG_TEST_RERUNS": "3"}, clear=False),
        patch.object(basic_checks, "_changed_python_files", return_value=(changed, True)),
        patch.object(basic_checks, "_tests_for_modules", return_value=targets),
        patch.object(basic_checks, "_plugin_available", return_value=True),
        patch.object(basic_checks, "_setting", return_value="auto"),
        patch.object(basic_checks, "_get_timeout", return_value=300),
        patch.object(basic_checks, "_run_subprocess") as mock_run,
    ):
        mock_run.return_value = (True, "ok")
        ok, _ = basic_checks.run_tests_incremental(base="HEAD")
        assert ok is True
        args, kwargs = mock_run.call_args
        cmd = args[0]
        # 应包含 --reruns 3
        assert "--reruns" in cmd
        idx = cmd.index("--reruns")
        assert cmd[idx + 1] == "3"
