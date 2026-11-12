"""P-02: LSP 增量诊断缓存 — didChange/didSave/didClose 失效，命中复用。

覆盖 ROADMAP P-02 "LSP 增量缓存"：诊断结果按 (文件内容 hash → diagnostics)
缓存，文档变更/保存/关闭后按新状态重新计算，避免重复跑整文件检查。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.lsp.server import AdgLanguageServer  # noqa: E402
from tools.scripts.adg_cli import check_file as _real_check_file  # noqa: E402


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


def _diagnose(server: AdgLanguageServer, uri: str) -> list[dict]:
    return server.handle_request("textDocument/diagnostic", {"textDocument": {"uri": uri}})


class TestLspIncrementalDiagnosticCache:
    def test_diagnostic_result_is_cached_and_reused(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        """同一文档连续诊断：check_file 只跑一次，结果一致。"""
        uri = f"file://{tmp_python_file}"
        with patch("tools.lsp.server.check_file", wraps=_real_check_file) as mock_check:
            first = _diagnose(server, uri)
            second = _diagnose(server, uri)

        assert mock_check.call_count == 1
        assert first == second

    def test_did_change_invalidates_cache(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        """didChange 后缓存失效，下次诊断重新计算。"""
        uri = f"file://{tmp_python_file}"
        with patch("tools.lsp.server.check_file", wraps=_real_check_file) as mock_check:
            _diagnose(server, uri)
            assert mock_check.call_count == 1

            server.handle_request(
                "textDocument/didChange",
                {"textDocument": {"uri": uri}, "contentChanges": [{"text": "def foo():\n    pass\n"}]},
            )
            _diagnose(server, uri)

        assert mock_check.call_count == 2

    def test_did_save_invalidates_cache(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        """didSave 后缓存失效，下次诊断重新计算。"""
        uri = f"file://{tmp_python_file}"
        with patch("tools.lsp.server.check_file", wraps=_real_check_file) as mock_check:
            _diagnose(server, uri)
            assert mock_check.call_count == 1

            server.handle_request("textDocument/didSave", {"textDocument": {"uri": uri}})
            _diagnose(server, uri)

        assert mock_check.call_count == 2

    def test_did_close_clears_cache(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        """didClose 后缓存条目清除，下次诊断重新计算。"""
        uri = f"file://{tmp_python_file}"
        with patch("tools.lsp.server.check_file", wraps=_real_check_file) as mock_check:
            _diagnose(server, uri)
            assert mock_check.call_count == 1

            server.handle_request("textDocument/didClose", {"textDocument": {"uri": uri}})
            _diagnose(server, uri)

        assert mock_check.call_count == 2
