"""AI-Native SDLC MCP (Model Context Protocol) Server (Phase 3)

Exposes semantic code queries, architecture guard checks, and red-team debates
as standard Model Context Protocol tools for AI assistants (Claude, Cursor, etc.).
"""

from __future__ import annotations

import json
import sys

from tools.scripts._common import get_project_root

# 工具元数据注册表：新增工具时同步维护，供 list_tools 发现接口返回
TOOL_REGISTRY: list[dict[str, object]] = [
    {
        "name": "query_semantic_graph",
        "description": "查询语义代码图中的符号及其依赖关系",
        "arguments": {"symbol": {"type": "string", "required": True, "description": "要查找的符号名（子串匹配）"}},
    },
    {
        "name": "run_architecture_guard",
        "description": "运行架构漂移守卫，检查分层违规",
        "arguments": {},
    },
    {
        "name": "knowledge_search",
        "description": "全文检索 docs/ 下知识库文档（BM25+同义词+jieba 中文分词），返回标题、摘要、评分与路径",
        "arguments": {
            "query": {"type": "string", "required": True, "description": "查询词（中英文均可）"},
            "limit": {"type": "integer", "required": False, "description": "返回条数，默认 5，上限 20"},
        },
    },
]


class AINativeMCPServer:
    def __init__(self) -> None:
        self.root_dir = get_project_root()
        self._search_index: object | None = None

    def _get_search_index(self) -> object:
        """惰性构建知识库索引（首次调用时加载，后续复用）。"""
        if self._search_index is None:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "adg_search_server", self.root_dir / "scripts/search-server.py"
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            from tools.scripts.search.tfidf_engine import create_enhanced_index

            self._search_index = create_enhanced_index(mod.load_documents())
        return self._search_index

    def handle_request(self, req: dict[str, object]) -> dict[str, object]:
        """处理单条 JSON-RPC 2.0 请求，返回带 id 的响应。

        支持方法：initialize / tools/list / tools/call / ping；
        同时兼容旧协议（裸 tool/arguments 字段）。
        """
        req_id = req.get("id")
        method = req.get("method")
        raw_params = req.get("params")
        params: dict[str, object] = raw_params if isinstance(raw_params, dict) else {}

        if "tool" not in req and isinstance(method, str):
            # 标准 JSON-RPC 2.0 分支
            result: dict[str, object]
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ai-native-sdlc", "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": TOOL_REGISTRY}
            elif method == "ping":
                result = {}
            elif method == "tools/call":
                raw_name = params.get("name")
                name: str | None = raw_name if isinstance(raw_name, str) else None
                args = params.get("arguments", {})
                call_res = self.handle_tool_call(name, args if isinstance(args, dict) else {})
                if call_res.get("status") == "success":
                    result = {
                        "content": [{"type": "text", "text": json.dumps(call_res, ensure_ascii=False)}],
                        "isError": False,
                    }
                else:
                    result = {
                        "content": [{"type": "text", "text": str(call_res.get("message", "error"))}],
                        "isError": True,
                    }
            else:
                return self._rpc_error(req_id, -32601, f"Method not found: {method}")
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        # 旧协议兼容分支：{tool, arguments} 裸字段
        raw_tool = req.get("tool") or params.get("name")
        tool: str | None = raw_tool if isinstance(raw_tool, str) else None
        args = req.get("arguments") or params.get("arguments", {})
        return self.handle_tool_call(tool, args if isinstance(args, dict) else {})

    @staticmethod
    def _rpc_error(req_id: object, code: int, message: str) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    def _tool_semantic_graph(self, arguments: dict[str, object]) -> dict[str, object]:
        symbol = arguments.get("symbol", "")
        graph_path = self.root_dir / ".semantic_graph.json"
        if not graph_path.exists():
            return {"status": "error", "message": "Semantic graph not built yet."}
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        matches = [v for k, v in data.items() if str(symbol) in k]
        return {"status": "success", "matches": matches[:10]}

    def _tool_knowledge_search(self, arguments: dict[str, object]) -> dict[str, object]:
        from tools.scripts.search.tfidf_engine import EnhancedTFIDF

        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"status": "error", "message": "missing 'query' argument"}
        try:
            raw_limit = arguments.get("limit", 5)
            limit = min(max(int(raw_limit), 1), 20) if isinstance(raw_limit, (int, str, float)) else 5
        except (TypeError, ValueError):
            limit = 5
        index = self._get_search_index()
        assert isinstance(index, EnhancedTFIDF)
        hits = index.search(query, top_k=limit)
        return {
            "status": "success",
            "total": len(hits),
            "results": [
                {
                    "id": h.doc.id,
                    "title": h.doc.title,
                    "snippet": h.snippet[:200],
                    "score": round(h.score, 4),
                    "category": h.doc.category,
                    "path": f"docs/{h.doc.id.replace('_', '/')}.md",
                }
                for h in hits
            ],
        }

    def _tool_architecture_guard(self, arguments: dict[str, object]) -> dict[str, object]:
        from tools.scripts.architecture_drift_guard import ArchitectureDriftGuard

        guard = ArchitectureDriftGuard(self.root_dir)
        violations = guard.check_layering()
        return {
            "status": "success",
            "violations": violations,
            "scanned_languages": guard.scanned_languages,
            "unsupported_languages": guard.unsupported_languages,
        }

    def handle_tool_call(self, tool_name: str | None, arguments: dict[str, object]) -> dict[str, object]:
        if tool_name == "list_tools":
            return {"status": "success", "tools": TOOL_REGISTRY}
        elif tool_name == "query_semantic_graph":
            return self._tool_semantic_graph(arguments)
        elif tool_name == "knowledge_search":
            return self._tool_knowledge_search(arguments)
        elif tool_name == "run_architecture_guard":
            return self._tool_architecture_guard(arguments)
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    server = AINativeMCPServer()
    print("🤖 AI-Native SDLC MCP Server initialized and ready.", file=sys.stderr)
    # stdin/stdout JSON-RPC 2.0 协议（兼容旧裸 tool 字段）
    for line in sys.stdin:
        try:
            req = json.loads(line)
            res = server.handle_request(req)
            print(json.dumps(res))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.stdout.flush()
