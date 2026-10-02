"""Tests for the self-correction main entry point."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

from self_correct import apply_fix, get_ai_fix, main, run_tests


class TestRunTests:
    @patch("self_correct.subprocess.run")
    def test_returns_tuple(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="boom", stderr="err")
        result = run_tests()
        assert isinstance(result, tuple)
        assert len(result) == 3
        returncode, stdout, stderr = result
        assert returncode == 1
        assert stdout == "boom"
        assert stderr == "err"


class TestGetAiFix:
    def test_returns_string(self) -> None:
        result = get_ai_fix("test error", "x = 1")
        assert isinstance(result, str)
        assert len(result) > 0


class TestApplyFix:
    def test_writes_to_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1")
            path = f.name
        try:
            apply_fix(path, "x = 2")
            with open(path) as f:
                content = f.read()
            assert content == "x = 2"
        finally:
            os.unlink(path)


class TestMain:
    @patch("self_correct.run_tests")
    def test_returns_on_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = (0, "", "")
        result = main()
        assert result is None or result == 0
