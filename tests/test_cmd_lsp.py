"""cmd_lsp 单元测试。

LSP 启动分支此前无覆盖(实测 33.3%)。重点: stdio/tcp 二选一、
log_level 经 getattr 解析、以及两种服务器异常都必须向上传播。
"""

from __future__ import annotations

import argparse
import logging
from unittest.mock import patch

import pytest

from tools.scripts.adg_cli.commands.cmd import cmd_lsp as mod


def _args(**kw) -> argparse.Namespace:
    base = {"stdio": True, "port": 0, "log_level": "info"}
    base.update(kw)
    return argparse.Namespace(**base)


class TestServerSelection:
    def test_stdio_true_calls_stdio_server(self) -> None:
        with patch("tools.lsp.server.run_stdio_server") as stdio, patch(
            "tools.lsp.server.run_tcp_server"
        ) as tcp:
            assert mod.cmd_lsp(_args(stdio=True)) == 0
        stdio.assert_called_once_with()
        tcp.assert_not_called()

    def test_stdio_false_calls_tcp_with_port(self) -> None:
        with patch("tools.lsp.server.run_stdio_server") as stdio, patch(
            "tools.lsp.server.run_tcp_server"
        ) as tcp:
            assert mod.cmd_lsp(_args(stdio=False, port=9257)) == 0
        tcp.assert_called_once_with(9257)
        stdio.assert_not_called()


class TestLogLevel:
    @pytest.mark.parametrize("name", ["info", "debug", "warning", "error"])
    def test_level_name_resolved(self, name: str) -> None:
        with patch("tools.lsp.server.run_stdio_server"), patch.object(logging, "basicConfig") as cfg:
            mod.cmd_lsp(_args(log_level=name))
        assert cfg.call_args.kwargs["level"] == getattr(logging, name.upper())

    def test_uppercase_input_also_works(self) -> None:
        with patch("tools.lsp.server.run_stdio_server"), patch.object(logging, "basicConfig") as cfg:
            mod.cmd_lsp(_args(log_level="DEBUG"))
        assert cfg.call_args.kwargs["level"] == logging.DEBUG


class TestFailurePropagation:
    def test_stdio_failure_propagates(self) -> None:
        with patch("tools.lsp.server.run_stdio_server", side_effect=RuntimeError("bind-fail")):
            with pytest.raises(RuntimeError, match="bind-fail"):
                mod.cmd_lsp(_args())

    def test_tcp_failure_propagates(self) -> None:
        with patch("tools.lsp.server.run_tcp_server", side_effect=OSError("port-in-use")):
            with pytest.raises(OSError):
                mod.cmd_lsp(_args(stdio=False, port=80))

    def test_bad_log_level_raises(self) -> None:
        """非法 log_level 必须报错 —— getattr 回落 default 会静默吞掉配置错误。"""
        with patch("tools.lsp.server.run_stdio_server"):
            with pytest.raises(AttributeError):
                mod.cmd_lsp(_args(log_level="nonexistent_level"))
