"""AI-Native MCP Server 回归测试。

背景: run_architecture_guard 工具曾用裸模块名 `from architecture_drift_guard import ...`
导致 ImportError，工具从未真正可用。本测试固化三个工具调用的行为契约，
防止导入断链与协议回归。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scripts.ai_native_mcp_server import AINativeMCPServer  # noqa: E402


@pytest.fixture()
def server(tmp_path: Path) -> AINativeMCPServer:
    """带临时根目录的服务器实例（不依赖真实仓库数据）。"""
    s = AINativeMCPServer()
    s.root_dir = tmp_path
    return s


class TestSemanticGraphQuery:
    """query_semantic_graph 工具。"""

    def test_error_when_graph_missing(self, server: AINativeMCPServer) -> None:
        result = server.handle_tool_call("query_semantic_graph", {"symbol": "Foo"})
        assert result["status"] == "error"
        assert "not built" in result["message"]

    def test_returns_matching_symbols(self, server: AINativeMCPServer, tmp_path: Path) -> None:
        graph = {"QualityGate.check": {"file": "a.py"}, "QualityGate.run": {"file": "b.py"}}
        (tmp_path / ".semantic_graph.json").write_text(json.dumps(graph), encoding="utf-8")
        result: dict[str, Any] = server.handle_tool_call("query_semantic_graph", {"symbol": "QualityGate"})
        assert result["status"] == "success"
        assert len(result["matches"]) == 2

    def test_caps_matches_at_ten(self, server: AINativeMCPServer, tmp_path: Path) -> None:
        graph = {f"Sym{i}": {"file": f"{i}.py"} for i in range(20)}
        # 全部包含公共子串 "Sym"
        graph = {f"Sym{i}x": v for i, v in enumerate(graph.values())}
        (tmp_path / ".semantic_graph.json").write_text(json.dumps(graph), encoding="utf-8")
        result: dict[str, Any] = server.handle_tool_call("query_semantic_graph", {"symbol": "Sym"})
        assert len(result["matches"]) <= 10


class TestArchitectureGuard:
    """run_architecture_guard 工具：核心回归点（导入断链修复）。"""

    def test_tool_executes_without_importerror(self, server: AINativeMCPServer) -> None:
        """裸模块导入已修为 tools.scripts.architecture_drift_guard，不再 ImportError。"""
        result = server.handle_tool_call("run_architecture_guard", {})
        assert result["status"] == "success"
        assert isinstance(result["violations"], list)


class TestProtocol:
    """JSON-RPC stdin/stdout 协议桩。"""

    def test_unknown_tool_returns_error(self, server: AINativeMCPServer) -> None:
        result = server.handle_tool_call("nonexistent", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

    def test_stdin_loop_roundtrip(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        """模拟一行 JSON-RPC 请求获得一行 JSON 响应。"""
        import io

        req = json.dumps({"tool": "nonexistent", "arguments": {}})
        monkeypatch.setattr("sys.stdin", io.StringIO(req + "\n"))
        # __main__ 块逻辑内联执行（避免 import 时触发）
        server = AINativeMCPServer()
        for line in sys.stdin:
            parsed = json.loads(line)
            res = server.handle_tool_call(parsed.get("tool"), parsed.get("arguments", {}))
            print(json.dumps(res))
            break
        out = capsys.readouterr().out.strip()
        assert json.loads(out)["status"] == "error"


class TestListTools:
    """list_tools 发现接口。"""

    def test_lists_all_registered_tools(self, server: AINativeMCPServer) -> None:
        result = server.handle_tool_call("list_tools", {})
        assert result["status"] == "success"
        names = [t["name"] for t in result["tools"]]  # type: ignore[index,union-attr]
        assert "query_semantic_graph" in names
        assert "run_architecture_guard" in names

    def test_registry_entries_have_metadata(self, server: AINativeMCPServer) -> None:
        result = server.handle_tool_call("list_tools", {})
        for t in result["tools"]:  # type: ignore[union-attr]
            assert "description" in t
            assert "arguments" in t


class TestProtocolCompat:
    """stdin 协议：裸 tool 字段与 MCP 风格 params.name 双兼容。"""

    def test_mcp_style_params_dispatch(self, server: AINativeMCPServer) -> None:
        req = {"method": "tools/call", "params": {"name": "list_tools", "arguments": {}}}
        tool = req.get("tool") or (req.get("params", {}) or {}).get("name")
        args = req.get("arguments") or (req.get("params", {}) or {}).get("arguments", {})
        result = server.handle_tool_call(tool, args)
        assert result["status"] == "success"


class TestJSONRPC20:
    """标准 JSON-RPC 2.0 协议（initialize/tools/list/tools/call/ping）。"""

    def test_initialize_returns_protocol_info(self, server: AINativeMCPServer) -> None:
        res = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert res["jsonrpc"] == "2.0"
        assert res["id"] == 1
        assert res["result"]["protocolVersion"] == "2024-11-05"
        assert res["result"]["serverInfo"]["name"] == "ai-native-sdlc"

    def test_tools_list_via_rpc(self, server: AINativeMCPServer) -> None:
        res = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = res["result"]["tools"]
        assert isinstance(tools, list) and len(tools) >= 2

    def test_ping_returns_empty_result(self, server: AINativeMCPServer) -> None:
        res = server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "ping"})
        assert res["result"] == {}

    def test_tools_call_success_wraps_content(self, server: AINativeMCPServer) -> None:
        req = {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_tools", "arguments": {}}}
        result = server.handle_request(req)["result"]
        assert result["isError"] is False
        assert json.loads(result["content"][0]["text"])["status"] == "success"

    def test_unknown_method_returns_error_code(self, server: AINativeMCPServer) -> None:
        res = server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "no/such"})
        assert res["error"]["code"] == -32601

    def test_legacy_tool_field_still_works(self, server: AINativeMCPServer) -> None:
        """旧协议（裸 tool 字段）回归保护。"""
        res = server.handle_request({"tool": "list_tools", "arguments": {}})
        assert res["status"] == "success"
