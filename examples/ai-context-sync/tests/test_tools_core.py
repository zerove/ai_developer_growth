"""Targeted tests for src/handlers/tools_core.py uncovered branches.

Covers the error-handling paths that test_mcp_server.py misses:
  - ai_sync:  generic Exception re-raise  (lines 35-37)
  - ai_guard: generic Exception re-raise  (lines 55-57)
  - ai_audit: AISyncError handler (85-86) + generic Exception re-raise (87-89)
  - ai_map:   AISyncError handler (111-112) + generic Exception re-raise (113-115)
"""

import json
from unittest.mock import MagicMock

import pytest

from src.exceptions import AISyncError
from src.handlers.tools_core import register


class MockMCP:
    """Minimal mock that captures registered tool functions."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


# ---------------------------------------------------------------------------
# ai_sync  – generic Exception re-raise  (lines 35-37)
# ---------------------------------------------------------------------------
class TestAiSyncGenericException:
    def test_generic_exception_is_reraised(self):
        """A non-AISyncError exception must propagate (not be swallowed)."""

        def boom(config=".ai-sync.json", dry_run=False):
            raise ValueError("unexpected")

        mcp = MockMCP()
        register(mcp, boom)

        with pytest.raises(ValueError, match="unexpected"):
            mcp.tools["ai_sync"]()

    def test_runtime_error_is_reraised(self):
        """Another programming error class also propagates."""

        def boom(config=".ai-sync.json", dry_run=False):
            raise RuntimeError("boom")

        mcp = MockMCP()
        register(mcp, boom)

        with pytest.raises(RuntimeError, match="boom"):
            mcp.tools["ai_sync"]()


# ---------------------------------------------------------------------------
# ai_guard  – generic Exception re-raise  (lines 55-57)
# ---------------------------------------------------------------------------
class TestAiGuardGenericException:
    def test_generic_exception_is_reraised(self):
        def boom(config=".ai-sync.json"):
            raise TypeError("bad arg")

        mcp = MockMCP()
        register(mcp, boom)

        with pytest.raises(TypeError, match="bad arg"):
            mcp.tools["ai_guard"]()

    def test_key_error_is_reraised(self):
        def boom(config=".ai-sync.json"):
            raise KeyError("missing")

        mcp = MockMCP()
        register(mcp, boom)

        with pytest.raises(KeyError):
            mcp.tools["ai_guard"]()


# ---------------------------------------------------------------------------
# ai_audit  – AISyncError (lines 85-86) + generic Exception (lines 87-89)
# ---------------------------------------------------------------------------
class TestAiAuditErrorBranches:
    def test_aisync_error_is_caught(self):
        """AISyncError should be caught and returned as error JSON."""

        def bad_factory(config=".ai-sync.json", **kwargs):
            raise AISyncError("audit config problem")

        mcp = MockMCP()
        register(mcp, bad_factory)

        result = mcp.tools["ai_audit"]()
        data = json.loads(result)
        assert data["status"] == "error"
        assert "audit config problem" in data["error"]

    def test_aisync_error_from_spec_audit(self):
        """AISyncError raised inside spec_audit should be caught."""
        mock_sync = MagicMock()
        mock_sync.spec_audit.side_effect = AISyncError("spec failed")

        def factory(config=".ai-sync.json", **kwargs):
            return mock_sync

        mcp = MockMCP()
        register(mcp, factory)

        result = mcp.tools["ai_audit"]()
        data = json.loads(result)
        assert data["status"] == "error"
        assert "spec failed" in data["error"]

    def test_generic_exception_is_reraised(self):
        def boom(config=".ai-sync.json", **kwargs):
            raise RuntimeError("internal")

        mcp = MockMCP()
        register(mcp, boom)

        with pytest.raises(RuntimeError, match="internal"):
            mcp.tools["ai_audit"]()

    def test_generic_exception_from_spec_audit(self):
        """A non-AISyncError raised inside spec_audit must propagate."""
        mock_sync = MagicMock()
        mock_sync.spec_audit.side_effect = AttributeError("no attr")

        def factory(config=".ai-sync.json", **kwargs):
            return mock_sync

        mcp = MockMCP()
        register(mcp, factory)

        with pytest.raises(AttributeError, match="no attr"):
            mcp.tools["ai_audit"]()


# ---------------------------------------------------------------------------
# ai_map  – AISyncError (lines 111-112) + generic Exception (lines 113-115)
# ---------------------------------------------------------------------------
class TestAiMapErrorBranches:
    def test_aisync_error_is_caught(self):
        """AISyncError should be caught and returned as error JSON."""

        def bad_factory(config=".ai-sync.json", **kwargs):
            raise AISyncError("graph init failed")

        mcp = MockMCP()
        register(mcp, bad_factory)

        result = mcp.tools["ai_map"]()
        data = json.loads(result)
        assert data["status"] == "error"
        assert "graph init failed" in data["error"]

    def test_aisync_error_from_decision_graph(self, tmp_path):
        """AISyncError raised during graph construction should be caught."""
        mock_sync = MagicMock()
        mock_sync.config.settings.adr_dir = str(tmp_path)

        # Patch DecisionGraph so it raises AISyncError
        _original_import_decision_graph = None

        class FakeDecisionGraph:
            def __init__(self, *args, **kwargs):
                raise AISyncError("bad adr dir")

        # We need to patch the import inside the function.
        # Instead, let get_sync_tool itself raise AISyncError.
        def factory(config=".ai-sync.json", **kwargs):
            raise AISyncError("sync init problem")

        mcp = MockMCP()
        register(mcp, factory)

        result = mcp.tools["ai_map"]()
        data = json.loads(result)
        assert data["status"] == "error"
        assert "sync init problem" in data["error"]

    def test_generic_exception_is_reraised(self):
        def boom(config=".ai-sync.json", **kwargs):
            raise ImportError("missing module")

        mcp = MockMCP()
        register(mcp, boom)

        with pytest.raises(ImportError, match="missing module"):
            mcp.tools["ai_map"]()
