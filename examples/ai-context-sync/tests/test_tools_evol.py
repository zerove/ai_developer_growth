"""Tests for MCP tool handlers: ai_evolve, ai_scaffold (tools_evol.py)."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.handlers.tools_evol import register

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_stub():
    """Return a stub mcp object and a list of registered tool callables."""
    registered = []

    class FakeMCP:
        def tool(self):
            def decorator(fn):
                registered.append(fn)
                return fn

            return decorator

    return FakeMCP(), registered


# ---------------------------------------------------------------------------
# ai_evolve
# ---------------------------------------------------------------------------


class TestAiEvolve:
    """Tests for the ai_evolve MCP tool handler."""

    def _register(self, get_sync_tool=None):
        """Register tools and return the ai_evolve callable."""
        mcp, fns = _make_mcp_stub()
        stub = get_sync_tool or (lambda **kw: MagicMock())
        register(mcp, stub)
        # ai_evolve is the first registered fn
        return fns[0]

    def test_no_candidates(self):
        """ai_evolve returns empty candidates when no conflicts detected."""
        evolve = MagicMock()
        evolve.analyze_conflicts.return_value = []
        sync = MagicMock()
        sync.evolution = evolve

        ai_evolve = self._register(get_sync_tool=lambda **kw: sync)
        result = json.loads(ai_evolve())

        assert result["status"] == "success"
        assert result["candidates"] == []
        assert "No evolution opportunities" in result["message"]

    def test_batch_true(self):
        """ai_evolve batch=True produces a single batch proposal."""
        candidates = [
            {"rule_id": "R1", "ratio": 0.8},
            {"rule_id": "R2", "ratio": 0.6},
        ]
        evolve = MagicMock()
        evolve.analyze_conflicts.return_value = candidates
        evolve.propose_batch_evolution.return_value = {
            "action": "update",
            "rules": ["R1", "R2"],
        }
        sync = MagicMock()
        sync.evolution = evolve

        ai_evolve = self._register(get_sync_tool=lambda **kw: sync)
        result = json.loads(ai_evolve(batch=True))

        assert result["status"] == "success"
        assert result["candidates"] == candidates
        assert result["batch_proposal"] == {"action": "update", "rules": ["R1", "R2"]}
        evolve.propose_batch_evolution.assert_called_once_with(candidates)

    def test_batch_false_multiple_candidates(self):
        """ai_evolve batch=False proposes each candidate individually."""
        candidates = [
            {"rule_id": "R1", "ratio": 0.9},
            {"rule_id": "R3", "ratio": 0.7},
        ]
        evolve = MagicMock()
        evolve.analyze_conflicts.return_value = candidates
        evolve.propose_evolution.side_effect = [
            {"suggestion": "relax R1"},
            {"suggestion": "update R3"},
        ]
        sync = MagicMock()
        sync.evolution = evolve

        ai_evolve = self._register(get_sync_tool=lambda **kw: sync)
        result = json.loads(ai_evolve(batch=False))

        assert result["status"] == "success"
        assert len(result["proposals"]) == 2
        assert result["proposals"][0]["rule_id"] == "R1"
        assert result["proposals"][0]["ratio"] == 0.9
        assert result["proposals"][0]["proposal"] == {"suggestion": "relax R1"}
        assert result["proposals"][1]["rule_id"] == "R3"
        assert evolve.propose_evolution.call_count == 2

    def test_exception_returns_error(self):
        """ai_evolve catches exceptions and returns error status."""

        def boom(**kw):
            raise RuntimeError("sync failed")

        ai_evolve = self._register(get_sync_tool=boom)
        result = json.loads(ai_evolve())

        assert result["status"] == "error"
        assert "sync failed" in result["error"]

    def test_custom_config_path(self):
        """ai_evolve passes config kwarg to get_sync_tool."""
        captured = {}

        def capture(**kw):
            captured.update(kw)
            sync = MagicMock()
            sync.evolution.analyze_conflicts.return_value = []
            return sync

        ai_evolve = self._register(get_sync_tool=capture)
        ai_evolve(config="custom.json")

        assert captured["config"] == "custom.json"


# ---------------------------------------------------------------------------
# ai_scaffold
# ---------------------------------------------------------------------------


class TestAiScaffold:
    """Tests for the ai_scaffold MCP tool handler."""

    def _register(self, get_sync_tool=None):
        """Register tools and return the ai_scaffold callable."""
        mcp, fns = _make_mcp_stub()
        stub = get_sync_tool or (lambda **kw: MagicMock())
        register(mcp, stub)
        # ai_scaffold is the second registered fn
        return fns[1]

    @patch("src.onboarding.OnboardingSession")
    def test_scaffold_success(self, MockSession):
        """ai_scaffold returns success when session starts cleanly."""
        sync = MagicMock()
        mock_session = MagicMock()
        MockSession.return_value = mock_session

        ai_scaffold = self._register(get_sync_tool=lambda **kw: sync)
        result = json.loads(ai_scaffold(template="python-fastapi", target_dir="/tmp/proj"))

        assert result["status"] == "success"
        assert result["template"] == "python-fastapi"
        assert result["target"] == "/tmp/proj"
        MockSession.assert_called_once_with(sync.llm_client, root_dir="/tmp/proj")
        mock_session.start.assert_called_once()

    @patch("src.onboarding.OnboardingSession")
    def test_scaffold_exception(self, MockSession):
        """ai_scaffold catches exceptions and returns error status."""
        MockSession.side_effect = RuntimeError("template not found")

        ai_scaffold = self._register(get_sync_tool=lambda **kw: MagicMock())
        result = json.loads(ai_scaffold(template="nonexistent"))

        assert result["status"] == "error"
        assert "template not found" in result["error"]

    @patch("src.onboarding.OnboardingSession")
    def test_scaffold_passes_dry_run_false(self, MockSession):
        """ai_scaffold passes dry_run=False to get_sync_tool."""
        captured = {}

        def capture(**kw):
            captured.update(kw)
            return MagicMock()

        ai_scaffold = self._register(get_sync_tool=capture)
        ai_scaffold(template="react-typescript")

        assert captured["dry_run"] is False
        assert captured["config"] == ".ai-sync.json"

    @patch("src.onboarding.OnboardingSession")
    def test_scaffold_custom_config(self, MockSession):
        """ai_scaffold passes custom config path to get_sync_tool."""
        captured = {}

        def capture(**kw):
            captured.update(kw)
            return MagicMock()

        ai_scaffold = self._register(get_sync_tool=capture)
        ai_scaffold(template="go-cli", config="my-config.json")

        assert captured["config"] == "my-config.json"
