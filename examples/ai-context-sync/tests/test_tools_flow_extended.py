"""Extended tests for src/handlers/tools_flow.py — cover ai_flow, ai_trace, ai_explain."""

import json
import os
import sys
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _register_and_capture(mock_get_sync):
    """Register tools and return dict of captured handler functions."""
    from src.handlers.tools_flow import register

    funcs = {}

    def capture_tool():
        def decorator(func):
            funcs[func.__name__] = func
            return func

        return decorator

    mock_mcp = MagicMock()
    mock_mcp.tool = capture_tool
    register(mock_mcp, get_sync_tool=mock_get_sync)
    return funcs


class TestToolsFlowRegister:
    """Test that register() wires up tool handlers on the mcp object."""

    def test_register_calls_mcp_tool_three_times(self):
        """register() decorates ai_flow, ai_trace, ai_explain = 3 calls."""
        from src.handlers.tools_flow import register

        mock_mcp = MagicMock()
        register(mock_mcp, get_sync_tool=MagicMock())
        assert mock_mcp.tool.call_count == 3

    def test_register_wires_all_three_handlers(self):
        """register() produces three decorated functions."""
        captured = []

        def capture_tool():
            def decorator(func):
                captured.append(func.__name__)
                return func

            return decorator

        mock_mcp = MagicMock()
        mock_mcp.tool = capture_tool
        from src.handlers.tools_flow import register

        register(mock_mcp, get_sync_tool=MagicMock())
        assert sorted(captured) == ["ai_explain", "ai_flow", "ai_trace"]


class TestAiFlowExtended:
    """Cover ai_flow: no-diff fallback, exception path, file parsing."""

    @patch("src.slicer.ContextSlicer")
    def test_ai_flow_no_diff_no_context_file(self, mock_slicer_cls):
        """ai_flow with empty diff and no aggregated context, context_file doesn't exist."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_flow = funcs["ai_flow"]

        mock_sync = MagicMock()
        mock_get_sync.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""
        mock_sync.analyzer.filter_diff.return_value = ""
        mock_sync.get_aggregated_context.return_value = ""
        mock_sync.config.settings.context_file = "/nonexistent/CONTEXT.md"
        mock_sync.orchestrator.run_flow.return_value = "result"

        with patch("src.handlers.tools_flow.os.path.exists", return_value=False):
            result_str = ai_flow(task="test task", config=".ai-sync.json")

        result = json.loads(result_str)
        assert result["status"] == "success"
        mock_sync.orchestrator.run_flow.assert_called_once()

    @patch("src.slicer.ContextSlicer")
    def test_ai_flow_no_diff_fallback_to_context_file(self, mock_slicer_cls):
        """ai_flow with empty diff, aggregated_context empty, but context_file exists."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_flow = funcs["ai_flow"]

        mock_sync = MagicMock()
        mock_get_sync.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""
        mock_sync.analyzer.filter_diff.return_value = ""
        mock_sync.get_aggregated_context.return_value = ""
        mock_sync.config.settings.context_file = "CONTEXT.md"
        mock_sync.orchestrator.run_flow.return_value = "flow_result"

        m = mock_open(read_data="# Root Context\nContent here.")
        with (
            patch("src.handlers.tools_flow.os.path.exists", return_value=True),
            patch("src.handlers.tools_flow.open", m),
        ):
            result_str = ai_flow(task="task", config=".ai-sync.json")

        result = json.loads(result_str)
        assert result["status"] == "success"

    @patch("src.slicer.ContextSlicer")
    def test_ai_flow_exception_returns_error(self, mock_slicer_cls):
        """ai_flow catches exceptions and returns error JSON."""
        mock_get_sync = MagicMock()
        mock_get_sync.side_effect = RuntimeError("sync init failed")
        funcs = _register_and_capture(mock_get_sync)
        ai_flow = funcs["ai_flow"]

        result_str = ai_flow(task="task", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "sync init failed" in result["error"]

    @patch("src.slicer.ContextSlicer")
    def test_ai_flow_with_diff_parsed_files(self, mock_slicer_cls):
        """ai_flow with diff lines containing +++ b/ parses affected files."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_flow = funcs["ai_flow"]

        mock_sync = MagicMock()
        mock_get_sync.return_value = mock_sync
        diff = "diff --git a/src/a.py b/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n+++ b/src/b.py\n"
        mock_sync.analyzer.get_last_commit_diff.return_value = diff
        mock_sync.analyzer.filter_diff.return_value = diff
        mock_sync.get_aggregated_context.return_value = "ctx"
        mock_sync.orchestrator.run_flow.return_value = "ok"

        result_str = ai_flow(task="task")
        result = json.loads(result_str)
        assert result["status"] == "success"
        call_args = mock_sync.get_aggregated_context.call_args[0][0]
        assert "src/a.py" in call_args
        assert "src/b.py" in call_args

    @patch("src.slicer.ContextSlicer")
    def test_ai_flow_aggregated_context_provided(self, mock_slicer_cls):
        """ai_flow uses aggregated_context when available (no file fallback)."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_flow = funcs["ai_flow"]

        mock_sync = MagicMock()
        mock_get_sync.return_value = mock_sync
        mock_sync.analyzer.get_last_commit_diff.return_value = ""
        mock_sync.analyzer.filter_diff.return_value = ""
        mock_sync.get_aggregated_context.return_value = "direct context"
        mock_sync.orchestrator.run_flow.return_value = "ok"

        result_str = ai_flow(task="task")
        result = json.loads(result_str)
        assert result["status"] == "success"
        call_kwargs = mock_sync.orchestrator.run_flow.call_args
        assert call_kwargs[1]["initial_context"] == "direct context"


class TestAiTraceExtended:
    """Cover ai_trace: empty chain, nodes with/without title, exception."""

    @patch("src.graph.DecisionGraph")
    def test_ai_trace_empty_chain(self, mock_graph_cls):
        """ai_trace returns not_found when chain is empty."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_trace = funcs["ai_trace"]

        mock_graph = MagicMock()
        mock_graph_cls.return_value = mock_graph
        mock_graph.trace_causality.return_value = []

        result_str = ai_trace(adr_id="ADR-999", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "not_found"
        assert result["adr_id"] == "ADR-999"

    @patch("src.graph.DecisionGraph")
    def test_ai_trace_chain_with_known_and_unknown_nodes(self, mock_graph_cls):
        """ai_trace handles nodes that exist in graph and unknown ones."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_trace = funcs["ai_trace"]

        mock_graph = MagicMock()
        mock_graph_cls.return_value = mock_graph
        mock_graph.trace_causality.return_value = ["ADR-001", "ADR-002"]

        node1 = MagicMock()
        node1.title = "Use REST"
        mock_graph.nodes = {"ADR-001": node1}

        result_str = ai_trace(adr_id="ADR-001", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert len(result["chain"]) == 2
        assert result["chain"][0]["title"] == "Use REST"
        assert result["chain"][1]["title"] == "Unknown"

    @patch("src.graph.DecisionGraph")
    def test_ai_trace_exception(self, mock_graph_cls):
        """ai_trace returns error JSON on exception."""
        mock_get_sync = MagicMock()
        mock_get_sync.side_effect = Exception("graph load error")
        funcs = _register_and_capture(mock_get_sync)
        ai_trace = funcs["ai_trace"]

        result_str = ai_trace(adr_id="ADR-001", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "graph load error" in result["error"]

    @patch("src.graph.DecisionGraph")
    def test_ai_trace_all_known_nodes(self, mock_graph_cls):
        """ai_trace with all nodes present in graph."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_trace = funcs["ai_trace"]

        mock_graph = MagicMock()
        mock_graph_cls.return_value = mock_graph
        mock_graph.trace_causality.return_value = ["ADR-001", "ADR-002", "ADR-003"]

        node1 = MagicMock(title="First")
        node2 = MagicMock(title="Second")
        node3 = MagicMock(title="Third")
        mock_graph.nodes = {"ADR-001": node1, "ADR-002": node2, "ADR-003": node3}

        result_str = ai_trace(adr_id="ADR-001", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert [n["title"] for n in result["chain"]] == ["First", "Second", "Third"]


class TestAiExplainExtended:
    """Cover ai_explain: normal path and exception."""

    @patch("src.reasoning.DecisionReasoner")
    def test_ai_explain_success(self, mock_reasoner_cls):
        """ai_explain returns explanation on success."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_explain = funcs["ai_explain"]

        mock_sync = MagicMock()
        mock_get_sync.return_value = mock_sync
        mock_sync.config.settings.adr_dir = "docs/adr/"

        mock_reasoner = MagicMock()
        mock_reasoner_cls.return_value = mock_reasoner
        mock_reasoner.explain_decision.return_value = "Because we needed scalability."

        result_str = ai_explain(query="Why PostgreSQL?", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "scalability" in result["explanation"]

    @patch("src.reasoning.DecisionReasoner")
    def test_ai_explain_exception(self, mock_reasoner_cls):
        """ai_explain returns error on exception."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_explain = funcs["ai_explain"]

        mock_reasoner_cls.side_effect = Exception("LLM connection failed")

        result_str = ai_explain(query="Why?", config=".ai-sync.json")
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "LLM connection failed" in result["error"]

    @patch("src.reasoning.DecisionReasoner")
    def test_ai_explain_passes_correct_args(self, mock_reasoner_cls):
        """ai_explain passes query to reasoner.explain_decision."""
        mock_get_sync = MagicMock()
        funcs = _register_and_capture(mock_get_sync)
        ai_explain = funcs["ai_explain"]

        mock_sync = MagicMock()
        mock_get_sync.return_value = mock_sync
        mock_sync.config.settings.adr_dir = "docs/adr/"

        mock_reasoner = MagicMock()
        mock_reasoner_cls.return_value = mock_reasoner
        mock_reasoner.explain_decision.return_value = "answer"

        ai_explain(query="Why OAuth2?", config=".ai-sync.json")
        mock_reasoner.explain_decision.assert_called_once_with("Why OAuth2?")
