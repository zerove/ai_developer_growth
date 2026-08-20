"""Extended tests for src/tester.py — cover _sanitize_env, pytest fallback, timeout bytes, OSError."""

import os
import subprocess
from unittest.mock import MagicMock, patch

from src.tester import TestRunner


class TestSanitizeEnvExtended:
    """Cover _sanitize_env: verify all sensitive keys are removed."""

    def test_sanitize_env_removes_all_sensitive_keys(self):
        """All 6 sensitive keys are removed from environment."""
        runner = TestRunner()
        with patch.dict(
            os.environ,
            {
                "AI_SYNC_KEY": "sk-123",
                "OPENAI_API_KEY": "openai-key",
                "ANTHROPIC_API_KEY": "anthropic-key",
                "AWS_SECRET_ACCESS_KEY": "aws-secret",
                "GITHUB_TOKEN": "gh-token",
                "GH_TOKEN": "gh-token-2",
                "SAFE_KEY": "should-remain",
            },
        ):
            env = runner._sanitize_env()
            assert "AI_SYNC_KEY" not in env
            assert "OPENAI_API_KEY" not in env
            assert "ANTHROPIC_API_KEY" not in env
            assert "AWS_SECRET_ACCESS_KEY" not in env
            assert "GITHUB_TOKEN" not in env
            assert "GH_TOKEN" not in env
            assert env.get("SAFE_KEY") == "should-remain"

    def test_sanitize_env_pythonpath_set_to_empty(self):
        """PYTHONPATH is reset to empty string."""
        runner = TestRunner()
        with patch.dict(os.environ, {"PYTHONPATH": "/some/path"}):
            env = runner._sanitize_env()
            assert env["PYTHONPATH"] == ""

    def test_sanitize_env_no_sensitive_keys(self):
        """When no sensitive keys exist, env is copied with PYTHONPATH reset."""
        runner = TestRunner()
        with patch.dict(os.environ, {"CLEAN_KEY": "value"}, clear=True):
            env = runner._sanitize_env()
            assert env.get("CLEAN_KEY") == "value"
            assert env["PYTHONPATH"] == ""


class TestRunTestPytestFallback:
    """Cover the pytest-not-found → unittest fallback path."""

    def test_pytest_not_found_falls_back_to_unittest(self):
        """When pytest is not found (FileNotFoundError), unittest is tried."""
        runner = TestRunner(timeout=10)

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1 and cmd[0] == "pytest":
                raise FileNotFoundError("pytest not found")
            result.returncode = 0
            result.stdout = "unittest output"
            result.stderr = ""
            return result

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("def test_pass(): pass", ["fake.py"])

        assert call_count == 2  # pytest first, then unittest
        assert result.success is True

    def test_pytest_fallback_unittest_also_fails_with_oserror(self):
        """When pytest not found and unittest raises OSError."""
        runner = TestRunner(timeout=10)

        def mock_run(cmd, **kwargs):
            if cmd[0] == "pytest":
                raise FileNotFoundError("pytest not found")
            raise OSError("cannot run process")

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("test", [])

        assert result.success is False
        assert "Execution failed" in result.output

    def test_pytest_fallback_unittest_raises_subprocess_error(self):
        """When pytest not found and unittest raises SubprocessError."""
        runner = TestRunner(timeout=10)

        def mock_run(cmd, **kwargs):
            if cmd[0] == "pytest":
                raise FileNotFoundError("pytest not found")
            raise subprocess.SubprocessError("subprocess broke")

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("test", [])

        assert result.success is False
        assert "Execution failed" in result.output


class TestRunTestTimeoutExtended:
    """Cover subprocess.TimeoutExpired with bytes stdout decoding."""

    def test_timeout_with_bytes_stdout(self):
        """TimeoutExpired with bytes stdout is decoded properly."""
        runner = TestRunner(timeout=1)

        error = subprocess.TimeoutExpired(cmd="pytest", timeout=1)
        error.stdout = b"some test output\nbefore timeout"
        error.stderr = b"stderr here"

        def mock_run(cmd, **kwargs):
            raise error

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("import time; time.sleep(10)", [])

        assert result.success is False
        assert result.exit_code == 124
        assert "timed out" in result.output
        assert "some test output" in result.output

    def test_timeout_with_none_stdout(self):
        """TimeoutExpired with stdout=None still produces valid output."""
        runner = TestRunner(timeout=1)

        error = subprocess.TimeoutExpired(cmd="pytest", timeout=1)
        error.stdout = None

        def mock_run(cmd, **kwargs):
            raise error

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("test", [])

        assert result.success is False
        assert result.exit_code == 124

    def test_timeout_with_string_stdout(self):
        """TimeoutExpired with string stdout (already decoded) is preserved."""
        runner = TestRunner(timeout=1)

        error = subprocess.TimeoutExpired(cmd="pytest", timeout=1)
        error.stdout = "already a string"

        def mock_run(cmd, **kwargs):
            raise error

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("test", [])

        assert "already a string" in result.output


class TestRunTestOSError:
    """Cover OSError and SubprocessError in main try block."""

    def test_oserror_in_main_run(self):
        """OSError from pytest invocation returns error result."""
        runner = TestRunner(timeout=10)

        def mock_run(cmd, **kwargs):
            raise OSError("Permission denied")

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("test", [])

        assert result.success is False
        assert result.exit_code == -1
        assert "Unexpected error" in result.output

    def test_subprocess_error_in_main_run(self):
        """SubprocessError from pytest invocation returns error result."""
        runner = TestRunner(timeout=10)

        def mock_run(cmd, **kwargs):
            raise subprocess.SubprocessError("process failed")

        with (
            patch("src.tester.subprocess.run", side_effect=mock_run),
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.shutil.copy2"),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = runner.run_test("test", [])

        assert result.success is False
        assert result.exit_code == -1
        assert "Unexpected error" in result.output


class TestRunTestTargetFiles:
    """Cover target file copy behavior."""

    def test_missing_target_file_logs_warning(self):
        """Non-existent target file triggers warning but doesn't crash."""
        runner = TestRunner(timeout=10)

        with (
            patch("src.tester.os.path.exists", return_value=False),
            patch("src.tester.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            # Should not raise
            result = runner.run_test(
                "def test_ok(): assert True", ["nonexistent/file.py"]
            )

        assert isinstance(result.output, str)

    def test_make_sandbox_limits_returns_none_on_non_linux(self):
        """_make_sandbox_limits returns None on non-Linux platforms."""
        with patch("src.tester.sys.platform", "darwin"):
            result = TestRunner._make_sandbox_limits()
            assert result is None
