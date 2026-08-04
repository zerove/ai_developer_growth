"""Tests for src/handlers/resources.py — get_context, get_adr, get_specs MCP resources."""

import os
import shutil
import tempfile
from unittest.mock import MagicMock

from src.handlers.resources import register


class TestResourcesRegister:
    """Tests for MCP resource handlers registered via register()."""

    def setup_method(self):
        """Set up mock MCP server and sync tool factory."""
        self.mock_mcp = MagicMock()
        self.mock_sync = MagicMock()
        self.get_sync_tool = MagicMock(return_value=self.mock_sync)

        register(self.mock_mcp, self.get_sync_tool)

        # Extract registered handlers by name
        self._handlers = {}
        for call in self.mock_mcp.resource.call_args_list:
            call[0][0]
            call[1] if call[1] else {}
            # The decorator replaces the function; retrieve from mock_mcp calls
            # Actually, the resource decorator registers via mcp.resource(uri)(fn)
            # We need to capture the decorated function
            pass

    def _get_handler(self, uri_pattern):
        """Get the handler function registered for a URI pattern."""
        for call_args in self.mock_mcp.resource.call_args_list:
            if call_args[0][0] == uri_pattern:
                return call_args[0][1] if len(call_args[0]) > 1 else None
        return None

    def _extract_handlers(self):
        """Re-register and extract handler functions."""
        self.mock_mcp.reset_mock()
        handlers = {}

        def capturing_decorator(uri):
            def decorator(fn):
                handlers[uri] = fn
                return fn

            return decorator

        self.mock_mcp.resource.side_effect = capturing_decorator
        register(self.mock_mcp, self.get_sync_tool)
        return handlers

    def test_get_context_exists(self):
        handlers = self._extract_handlers()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Context\n\nProject context.")
            f.flush()
            tmp_path = f.name

        try:
            self.mock_sync.config.settings.context_file = tmp_path
            result = handlers["context://{config_path}"]()
            assert "Project context" in result
        finally:
            os.unlink(tmp_path)

    def test_get_context_missing(self):
        handlers = self._extract_handlers()
        self.mock_sync.config.settings.context_file = "/nonexistent/path.md"

        result = handlers["context://{config_path}"]()
        assert "No context file found" in result

    def test_get_context_error(self):
        handlers = self._extract_handlers()
        from src.exceptions import AISyncError

        self.get_sync_tool.side_effect = AISyncError("config error")

        result = handlers["context://{config_path}"]()
        assert "Error:" in result

    def test_get_adr_found(self):
        handlers = self._extract_handlers()
        tmpdir = tempfile.mkdtemp()
        try:
            adr_file = os.path.join(tmpdir, "001-decision.md")
            with open(adr_file, "w") as f:
                f.write("# ADR-001\n\nWe choose Python.")

            self.mock_sync.config.settings.adr_dir = tmpdir
            result = handlers["adr://{adr_id}"]("ADR-001")
            assert "We choose Python" in result
        finally:
            shutil.rmtree(tmpdir)

    def test_get_adr_not_found(self):
        handlers = self._extract_handlers()
        tmpdir = tempfile.mkdtemp()
        try:
            self.mock_sync.config.settings.adr_dir = tmpdir
            result = handlers["adr://{adr_id}"]("ADR-999")
            assert "not found" in result
        finally:
            shutil.rmtree(tmpdir)

    def test_get_adr_error(self):
        handlers = self._extract_handlers()
        self.get_sync_tool.side_effect = OSError("dir not found")

        result = handlers["adr://{adr_id}"]("ADR-001")
        assert "Error:" in result

    def test_get_specs_exists(self):
        handlers = self._extract_handlers()
        tmpdir = tempfile.mkdtemp()
        try:
            spec_file = os.path.join(tmpdir, "python.md")
            with open(spec_file, "w") as f:
                f.write("# Python Spec\n\nType hints required.")

            self.mock_sync.config.settings.specs_dir = tmpdir
            result = handlers["specs://{language}"]("python")
            assert "Type hints required" in result
        finally:
            shutil.rmtree(tmpdir)

    def test_get_specs_missing(self):
        handlers = self._extract_handlers()
        tmpdir = tempfile.mkdtemp()
        try:
            self.mock_sync.config.settings.specs_dir = tmpdir
            result = handlers["specs://{language}"]("rustlang")
            assert "No spec for rustlang" in result
        finally:
            shutil.rmtree(tmpdir)

    def test_get_specs_error(self):
        handlers = self._extract_handlers()
        self.get_sync_tool.side_effect = OSError("permission denied")

        result = handlers["specs://{language}"]("python")
        assert "Error:" in result
