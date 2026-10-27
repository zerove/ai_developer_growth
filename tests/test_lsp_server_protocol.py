# 拆分自 tests/test_lsp_server.py

"""LSP server 单元测试 — 不启动 stdio/TCP，只测 AdgLanguageServer 协议层。

覆盖 ROADMAP P1-4 "0% 模块测试攻坚"中 tools/lsp/server.py (510 行无单测)。

测试目标：
1. AdgLanguageServer 协议层 handle_request 路由
2. 各 _handle_* 协议方法的输入 → 输出映射
3. _get_rules 缓存命中
4. exclude_patterns / enable_quick_fix / enable_code_lens 等配置开关
5. 边界：未支持文件后缀、不存在文件、空 query、未知 method
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


from tools.lsp.server import (  # noqa: E402
    SUPPORTED_EXTENSIONS,
    AdgLanguageServer,
)


@pytest.fixture
def server() -> AdgLanguageServer:
    """返回干净的 AdgLanguageServer 实例。"""
    return AdgLanguageServer()


@pytest.fixture
def tmp_python_file(tmp_path: Path) -> Path:
    """创建一个临时的 Python 文件用于诊断测试。"""
    f = tmp_path / "sample.py"
    f.write_text("def foo():\n    pass\n")
    return f


class TestRulesCache:
    def test_cache_hit(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_rules_for_language", return_value={"anti_patterns": []}) as mock:
            server._get_rules("python")
            server._get_rules("python")
            server._get_rules("python")
        # 缓存命中：3 次调用只 1 次查 load_rules_for_language
        assert mock.call_count == 1

    def test_cache_per_language(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_rules_for_language", return_value={"anti_patterns": []}) as mock:
            server._get_rules("python")
            server._get_rules("rust")
        assert mock.call_count == 2


class TestSupportedExtensions:
    def test_python_in_registry(self) -> None:
        assert ".py" in SUPPORTED_EXTENSIONS
        assert SUPPORTED_EXTENSIONS[".py"] == "python"

    def test_registry_has_15_plus_languages(self) -> None:
        assert len(SUPPORTED_EXTENSIONS) >= 15


class TestReadMessage:
    """read_message() 从 stdin.buffer 读 Content-Length + body 帧。"""

    def test_valid_message(self, monkeypatch) -> None:
        from tools.lsp import server as lsp_server

        body = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        # 模拟 stdin.buffer：返回 header 行，然后空行，然后 body
        stdin_buffer = [
            header.split(b"\r\n")[0] + b"\r\n",
            header.split(b"\r\n")[1] + b"\r\n",
            body,
        ]

        def readline(self=None) -> bytes:
            return stdin_buffer.pop(0) if stdin_buffer else b""

        def read(self=None, n: int = 0) -> bytes:
            return stdin_buffer.pop(0)

        # 用 staticmethod 避免 self 绑定问题
        fake_stdin = type(
            "FakeStdin",
            (),
            {
                "readline": staticmethod(readline),
                "read": staticmethod(read),
            },
        )()
        monkeypatch.setattr(lsp_server.sys, "stdin", type("S", (), {"buffer": fake_stdin})())

        method, params, msg_id = lsp_server.read_message()
        assert method == "initialize"
        assert params == {}
        assert msg_id == 1

    def test_eof_raises_eof_error(self, monkeypatch) -> None:
        from tools.lsp import server as lsp_server

        fake_stdin = type(
            "FakeStdin",
            (),
            {
                "readline": staticmethod(lambda: b""),
            },
        )()
        monkeypatch.setattr(lsp_server.sys, "stdin", type("S", (), {"buffer": fake_stdin})())
        with pytest.raises(EOFError):
            lsp_server.read_message()

    def test_no_content_length_raises(self, monkeypatch) -> None:
        from tools.lsp import server as lsp_server

        # 读 header 正常但无 Content-Length，最后空行
        stdin_buffer = [b"\r\n", b"\r\n"]

        def readline() -> bytes:
            return stdin_buffer.pop(0) if stdin_buffer else b""

        fake_stdin = type(
            "FakeStdin",
            (),
            {
                "readline": staticmethod(readline),
            },
        )()
        monkeypatch.setattr(lsp_server.sys, "stdin", type("S", (), {"buffer": fake_stdin})())
        with pytest.raises(ValueError, match="No Content-Length"):
            lsp_server.read_message()


class TestWriteMessage:
    """write_message() 写 Content-Length + body 帧到 stdout.buffer。"""

    def test_writes_framed_message(self, monkeypatch) -> None:
        from tools.lsp import server as lsp_server

        captured: list[bytes] = []

        class FakeStdout:
            buffer = type(
                "B",
                (),
                {
                    "write": lambda self, data: captured.append(data),
                    "flush": lambda self: None,
                },
            )()

        monkeypatch.setattr(lsp_server.sys, "stdout", FakeStdout())

        lsp_server.write_message({"jsonrpc": "2.0", "id": 1, "result": "ok"})

        assert len(captured) == 1
        written = captured[0]
        # 含 Content-Length 头
        assert written.startswith(b"Content-Length: ")
        # 含 \r\n\r\n 分隔符
        assert b"\r\n\r\n" in written
        # body 末尾是 JSON
        body = written.split(b"\r\n\r\n", 1)[1]
        parsed = json.loads(body)
        assert parsed["result"] == "ok"


class TestSendNotification:
    """send_notification() 包装 write_message 添加 jsonrpc 字段。"""

    def test_writes_notification(self, monkeypatch) -> None:
        from tools.lsp import server as lsp_server

        captured: list[bytes] = []

        class FakeStdout:
            buffer = type(
                "B",
                (),
                {
                    "write": lambda self, data: captured.append(data),
                    "flush": lambda self: None,
                },
            )()

        monkeypatch.setattr(lsp_server.sys, "stdout", FakeStdout())

        lsp_server.send_notification("test/method", {"key": "value"})

        assert len(captured) == 1
        body = captured[0].split(b"\r\n\r\n", 1)[1]
        parsed = json.loads(body)
        assert parsed["method"] == "test/method"
        assert parsed["params"] == {"key": "value"}
