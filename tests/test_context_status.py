"""context_status 子命令测试: status / split"""

import subprocess
import sys

from tools.scripts.context_status import cmd_status


def test_cmd_status_returns_zero() -> None:
    """status 子命令应返回 0, 输出包含项目快照关键字段."""
    res = subprocess.run(
        [sys.executable, "-m", "tools.scripts.context_status", "status"],
        capture_output=True,
        text=True,
        cwd="/home/zeron/dev/ai_developer_growth",
    )
    assert res.returncode == 0
    out = res.stdout
    assert "Project Status Snapshot" in out
    assert "Version" in out
    assert "Recent commits" in out
    assert "Test files" in out


def test_cmd_status_in_unit_call() -> None:
    """直接调用 cmd_status() 也能跑通(无参数)."""
    code = cmd_status()
    assert code == 0
