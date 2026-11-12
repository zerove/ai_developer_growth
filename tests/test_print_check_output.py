"""`print_check` 的失败输出截断契约。

背景（真实失效形态）:
    历史实现只打印失败输出的**前 20 行**。pytest/mypy 的关键信息
    （失败用例名、汇总行、崩溃栈、`INTERNALERROR`）全在末尾, 于是 CI 日志
    里只剩"测试开始了"的样子, 看不到为什么失败 —— 排查只能靠本地重跑或猜。

    本文件同时是 `tests/test_common.py` 的容量缓冲: 后者已接近
    `test_test_file_size.py` 的 500 行上限, 新用例放这里而不是继续堆进去。
"""

from __future__ import annotations

import pytest

from tools.scripts._common import print_check


def test_long_failure_output_keeps_tail(capsys: pytest.CaptureFixture[str]) -> None:
    """超长输出截断时保留末尾, 并显式标注省略行数。"""
    lines = [f"line-{i}" for i in range(100)]
    print_check("Test", False, "\n".join(lines))
    output = capsys.readouterr().out
    assert "line-0" in output, "头部上下文应保留"
    assert "line-99" in output, "末尾的关键信息被丢弃"
    assert "省略" in output, "截断必须显式标注, 不能假装是完整输出"


def test_short_failure_output_is_complete(capsys: pytest.CaptureFixture[str]) -> None:
    """短输出不得被截断, 也不该出现省略提示。"""
    print_check("Test", False, "first\nsecond")
    output = capsys.readouterr().out
    assert "first" in output and "second" in output
    assert "省略" not in output


def test_passed_check_never_prints_output(capsys: pytest.CaptureFixture[str]) -> None:
    """通过时只输出一行结论, 不把成功日志刷进 CI。"""
    print_check("Test", True, "some noisy log")
    output = capsys.readouterr().out
    assert "some noisy log" not in output
