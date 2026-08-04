"""Extended tests for src/guard.py — cover _load_adrs, check_design_drift, check_drift_json."""

import os
import shutil
import tempfile
from unittest.mock import MagicMock

from src.guard import ArchitectureGuard


class TestLoadAdrsExtended:
    """Cover _load_adrs: empty dir, nonexistent dir, only non-.md files."""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_load_adrs_nonexistent_directory(self):
        """Non-existent directory returns 'No ADRs defined yet.'."""
        guard = ArchitectureGuard(self.mock_client, "/nonexistent/path/adr")
        result = guard._load_adrs()
        assert result == "No ADRs defined yet."

    def test_load_adrs_empty_directory(self):
        """Empty directory returns 'No ADRs defined yet.'."""
        tmpdir = tempfile.mkdtemp()
        try:
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            result = guard._load_adrs()
            assert result == "No ADRs defined yet."
        finally:
            shutil.rmtree(tmpdir)

    def test_load_adrs_only_non_md_files(self):
        """Directory with only non-.md files returns 'No ADRs defined yet.'."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "notes.txt"), "w") as f:
                f.write("some notes")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            result = guard._load_adrs()
            assert result == "No ADRs defined yet."
        finally:
            shutil.rmtree(tmpdir)

    def test_load_adrs_with_multiple_md_files(self):
        """Multiple .md files are loaded and joined."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: First decision")
            with open(os.path.join(tmpdir, "ADR-002.md"), "w") as f:
                f.write("# ADR-002: Second decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            result = guard._load_adrs()
            assert "ADR-001" in result
            assert "ADR-002" in result
        finally:
            shutil.rmtree(tmpdir)


class TestCheckDesignDriftExtended:
    """Cover check_design_drift: no ADRs early return, LLM empty response."""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_design_drift_no_adrs_returns_compliant(self):
        """When no ADRs exist, returns compliant message without calling LLM."""
        guard = ArchitectureGuard(self.mock_client, "/nonexistent/adr")
        result = guard.check_design_drift("design doc", "task")
        assert "compliant" in result.lower()
        self.mock_client.generate.assert_not_called()

    def test_design_drift_llm_empty_response_returns_error(self):
        """When LLM returns empty string, returns error message."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = ""
            result = guard.check_design_drift("design", "task")
            assert "Error" in result or "error" in result.lower()
        finally:
            shutil.rmtree(tmpdir)

    def test_design_drift_llm_none_response_returns_error(self):
        """When LLM returns None, returns error message."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = None
            result = guard.check_design_drift("design", "task")
            assert "Error" in result
        finally:
            shutil.rmtree(tmpdir)

    def test_design_drift_with_adrs_calls_llm(self):
        """When ADRs exist, calls LLM with proper prompt."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Use REST")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = "All design aspects are compliant."
            result = guard.check_design_drift("my design", "implement API")
            self.mock_client.generate.assert_called_once()
            assert "compliant" in result.lower()
        finally:
            shutil.rmtree(tmpdir)


class TestCheckDriftJsonExtended:
    """Cover check_drift_json: no ADRs, LLM non-JSON, empty violations."""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_drift_json_no_adrs_returns_empty(self):
        """No ADRs → returns empty list without LLM call."""
        guard = ArchitectureGuard(self.mock_client, "/nonexistent/adr")
        result = guard.check_drift_json("diff", "msg")
        assert result == []
        self.mock_client.generate.assert_not_called()

    def test_drift_json_llm_returns_non_json(self):
        """LLM returns non-JSON text → returns empty list."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = "This is not JSON at all, just plain text."
            result = guard.check_drift_json("diff", "msg")
            assert result == []
        finally:
            shutil.rmtree(tmpdir)

    def test_drift_json_llm_returns_empty_violations(self):
        """LLM returns valid empty JSON array → returns empty list."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = "[]"
            result = guard.check_drift_json("diff", "msg")
            assert result == []
        finally:
            shutil.rmtree(tmpdir)

    def test_drift_json_llm_returns_fenced_json(self):
        """LLM returns JSON in markdown fence → parsed correctly."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = (
                '```json\n[{"rule_id": "R1", "severity": "High", "description": "Bad", "adr_file": "f.md"}]\n```'
            )
            result = guard.check_drift_json("diff", "msg")
            assert len(result) == 1
            assert result[0]["rule_id"] == "R1"
        finally:
            shutil.rmtree(tmpdir)

    def test_drift_json_llm_returns_none(self):
        """LLM returns None → parse_llm_json returns None → fallback to []."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
                f.write("# ADR-001: Decision")
            guard = ArchitectureGuard(self.mock_client, tmpdir)
            self.mock_client.generate.return_value = None
            result = guard.check_drift_json("diff", "msg")
            assert result == []
        finally:
            shutil.rmtree(tmpdir)
