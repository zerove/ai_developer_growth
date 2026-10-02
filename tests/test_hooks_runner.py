"""Tests for hooks_runner.py - unified hook runner entry point.

Updated for modular architecture:
    - basic_checks: lint, format, typecheck, test, security
    - domain_checks: language-rules, quality-gate, governance-audit
    - incremental_checks: diff, pre-commit, git helpers
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scripts.hooks_runner import (
    get_changed_files,
    get_staged_files,
    run_diff_checks,
    run_format_check,
    run_governance_audit,
    run_language_rules,
    run_lint,
    run_pre_commit_checks,
    run_quality_gate,
    run_security,
    run_tests,
    run_typecheck,
)


def _mock_process(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Create a mock subprocess.CompletedProcess."""
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestRunLint(unittest.TestCase):
    """Test run_lint function."""

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_lint_pass(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(0, "All checks passed!")
        passed, output = run_lint()
        self.assertTrue(passed)
        self.assertIn("All checks passed", output)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "ruff")
        self.assertIn("check", args)

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_lint_fail(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(1, "", "E501 line too long")
        passed, output = run_lint()
        self.assertFalse(passed)
        self.assertIn("E501", output)


class TestRunFormatCheck(unittest.TestCase):
    """Test run_format_check function."""

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_format_pass(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(0, "293 files already formatted")
        passed, output = run_format_check()
        self.assertTrue(passed)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("--check", args)

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_format_fail(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(1, "", "Would reformat: foo.py")
        passed, output = run_format_check()
        self.assertFalse(passed)


class TestRunTypecheck(unittest.TestCase):
    """Test run_typecheck function."""

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_typecheck_pass(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(0, "Success: no issues found")
        passed, output = run_typecheck()
        self.assertTrue(passed)
        args = mock_run.call_args[0][0]
        self.assertIn("mypy", " ".join(str(a) for a in args))

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_typecheck_fail(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(1, "", "Found 1 error")
        passed, output = run_typecheck()
        self.assertFalse(passed)


class TestRunTests(unittest.TestCase):
    """Test run_tests function."""

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_tests_pass(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(0, "748 passed")
        passed, output = run_tests()
        self.assertTrue(passed)
        args = mock_run.call_args[0][0]
        self.assertIn("pytest", " ".join(str(a) for a in args))

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_tests_fail(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_process(1, "", "FAILED tests/test_foo.py")
        passed, output = run_tests()
        self.assertFalse(passed)


class TestRunSecurity(unittest.TestCase):
    """Test run_security function."""

    @patch("tools.scripts.hooks.basic_checks.scan_secrets")
    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_security_pass(self, mock_run: MagicMock, mock_scan: MagicMock) -> None:
        from tools.scripts.secret_scanner import SecretScanResult

        mock_run.return_value = _mock_process(0, '{"results": []}')
        mock_scan.return_value = SecretScanResult(findings=[], tools_used=["builtin"])
        passed, output = run_security()
        self.assertTrue(passed)
        # Called twice: bandit + pip-audit (secret scan is in-process)
        self.assertEqual(mock_run.call_count, 2)

    @patch("tools.scripts.hooks.basic_checks.scan_secrets")
    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_security_bandit_fails(self, mock_run: MagicMock, mock_scan: MagicMock) -> None:
        from tools.scripts.secret_scanner import SecretScanResult

        mock_scan.return_value = SecretScanResult(findings=[], tools_used=["builtin"])
        mock_run.side_effect = [
            _mock_process(1, "", "Issue found"),
            _mock_process(0, ""),
        ]
        passed, output = run_security()
        self.assertFalse(passed)
        self.assertIn("bandit", output)


class TestRunLanguageRules(unittest.TestCase):
    """Test run_language_rules function."""

    def test_language_rules_file_not_found(self) -> None:
        """Test with non-existent path goes to directory branch."""
        nonexistent = Path("/nonexistent/dir")
        # path.is_file() returns False, so it goes to validate_directory
        # which will return empty results for non-existent dir
        passed, output = run_language_rules(nonexistent)
        # Empty directory = pass (no files to check)
        self.assertTrue(passed)

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_language_rules_no_detect(self, mock_detect: MagicMock) -> None:
        """Test when language cannot be detected."""
        mock_detect.return_value = None
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test content")
            f.flush()
            passed, output = run_language_rules(Path(f.name))
            self.assertFalse(passed)
            self.assertIn("Cannot detect language", output)
        Path(f.name).unlink(missing_ok=True)


class TestRunQualityGate(unittest.TestCase):
    """Test run_quality_gate function."""

    def test_quality_gate_no_files(self) -> None:
        """Test with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            passed, output = run_quality_gate(Path(tmpdir))
            self.assertTrue(passed)
            self.assertIn("No files", output)

    def test_quality_gate_full_mode(self) -> None:
        """Test full mode includes all checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python file
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("# simple test\nx = 1\n")
            passed, output = run_quality_gate(Path(tmpdir), full=True)
            # Should not crash
            self.assertIsInstance(output, str)

    def test_quality_gate_json_format(self) -> None:
        """Test JSON output format with a file present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("# simple test\nx = 1\n")
            passed, output = run_quality_gate(Path(tmpdir), format="json")
            import json

            data = json.loads(output)
            self.assertIn("summary", data)

    def test_quality_gate_specific_check(self) -> None:
        """Test with specific check enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("# simple test\nx = 1\n")
            passed, output = run_quality_gate(Path(tmpdir), check_annotation=True)
            self.assertIsInstance(output, str)


class TestRunGovernanceAudit(unittest.TestCase):
    """Test run_governance_audit function."""

    @patch("tools.scripts.hooks.domain_checks.Path")
    def test_governance_audit_import_fails(self, mock_path: MagicMock) -> None:
        """Test governance audit when module import fails."""
        # This tests the ImportError path
        mock_path.return_value.resolve.return_value.parent.parent.parent = Path("/nonexistent")
        # The function will raise ImportError due to missing module
        try:
            ok, output = run_governance_audit(validate_docs=True)
        except (ImportError, FileNotFoundError):
            return  # 显式抛出也是可接受的失败路径
        # 若它吞掉了异常，则绝不能把"加载失败"报告成通过
        assert ok is False, f"加载失败时不得报告通过: {output}"


class TestMainCLI(unittest.TestCase):
    """Test CLI argument parsing and dispatch."""

    def test_main_lint_command(self) -> None:
        """Test lint command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "lint"]):
            with patch("tools.scripts.hooks_runner.run_lint", return_value=(True, "ok")) as mock:
                result = main()
                self.assertEqual(result, 0)
                mock.assert_called_once()

    def test_main_format_command(self) -> None:
        """Test format command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "format"]):
            with patch("tools.scripts.hooks_runner.run_format_check", return_value=(True, "ok")):
                result = main()
                self.assertEqual(result, 0)

    def test_main_typecheck_command(self) -> None:
        """Test typecheck command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "typecheck"]):
            with patch("tools.scripts.hooks_runner.run_typecheck", return_value=(True, "ok")):
                result = main()
                self.assertEqual(result, 0)

    def test_main_test_command(self) -> None:
        """Test test command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "test"]):
            with patch("tools.scripts.hooks_runner.run_tests", return_value=(True, "ok")):
                result = main()
                self.assertEqual(result, 0)

    def test_main_security_command(self) -> None:
        """Test security command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "security"]):
            with patch("tools.scripts.hooks_runner.run_security", return_value=(True, "ok")):
                result = main()
                self.assertEqual(result, 0)

    def test_main_language_rules_command(self) -> None:
        """Test language-rules command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "language-rules", "--path", "."]):
            with patch(
                "tools.scripts.hooks_runner.run_language_rules",
                return_value=(True, "ok"),
            ):
                result = main()
                self.assertEqual(result, 0)

    def test_main_quality_gate_command(self) -> None:
        """Test quality-gate command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "quality-gate", "--path", ".", "--full"]):
            with patch("tools.scripts.hooks_runner.run_quality_gate", return_value=(True, "ok")):
                result = main()
                self.assertEqual(result, 0)

    def test_main_governance_audit_command(self) -> None:
        """Test governance-audit command dispatch."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "governance-audit", "--full"]):
            with patch(
                "tools.scripts.hooks_runner.run_governance_audit",
                return_value=(True, "ok"),
            ):
                result = main()
                self.assertEqual(result, 0)

    def test_main_full_command(self) -> None:
        """Test full command runs all checks."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "full"]):
            with patch("tools.scripts.hooks_runner.run_lint", return_value=(True, "ok")):
                with patch(
                    "tools.scripts.hooks_runner.run_format_check",
                    return_value=(True, "ok"),
                ):
                    with patch(
                        "tools.scripts.hooks_runner.run_typecheck",
                        return_value=(True, "ok"),
                    ):
                        with patch(
                            "tools.scripts.hooks_runner.run_tests",
                            return_value=(True, "ok"),
                        ):
                            with patch(
                                "tools.scripts.hooks_runner.run_security",
                                return_value=(True, "ok"),
                            ):
                                with patch(
                                    "tools.scripts.hooks_runner.run_quality_gate",
                                    return_value=(True, "ok"),
                                ):
                                    with patch(
                                        "tools.scripts.hooks_runner.run_governance_audit",
                                        return_value=(True, "ok"),
                                    ):
                                        result = main()
                                        self.assertEqual(result, 0)

    def test_main_lint_fails(self) -> None:
        """Test lint failure returns exit code 1."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "lint"]):
            with patch("tools.scripts.hooks_runner.run_lint", return_value=(False, "errors")):
                result = main()
                self.assertEqual(result, 1)

    def test_main_diff(self) -> None:
        """Test diff command invokes run_diff_checks."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "diff"]):
            with patch("tools.scripts.hooks_runner.run_diff_checks", return_value=(True, "ok")):
                result = main()
                self.assertEqual(result, 0)

    def test_main_diff_fails(self) -> None:
        """Test diff failure returns exit code 1."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "diff"]):
            with patch(
                "tools.scripts.hooks_runner.run_diff_checks",
                return_value=(False, "errors"),
            ):
                result = main()
                self.assertEqual(result, 1)

    def test_main_pre_commit(self) -> None:
        """Test pre-commit command invokes run_pre_commit_checks."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "pre-commit"]):
            with patch(
                "tools.scripts.hooks_runner.run_pre_commit_checks",
                return_value=(True, "ok"),
            ):
                result = main()
                self.assertEqual(result, 0)

    def test_main_docs_validate(self) -> None:
        """Test docs-validate unified entry invokes governance-docs-validator."""
        from tools.scripts.hooks_runner import main

        with patch("sys.argv", ["hooks_runner.py", "docs-validate"]):
            with patch(
                "tools.scripts.hooks_runner._handle_docs_validate",
            ) as mock_handle:
                mock_handle.return_value = 0
                result = main()
                self.assertEqual(result, 0)
                mock_handle.assert_called_once()


class TestDiffAndPreCommit(unittest.TestCase):
    """Tests for incremental check functions."""

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_returns_paths(self, mock_run: MagicMock) -> None:
        """Test get_changed_files returns Path objects."""
        mock_run.return_value = _mock_process(0, "file1.py\nfile2.ts\n")
        files = get_changed_files("HEAD")
        self.assertEqual(len(files), 2)
        self.assertIsInstance(files[0], Path)

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_empty(self, mock_run: MagicMock) -> None:
        """Test get_changed_files with no changes."""
        mock_run.return_value = _mock_process(0, "")
        files = get_changed_files("HEAD")
        self.assertEqual(files, [])

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_staged_files(self, mock_run: MagicMock) -> None:
        """Test get_staged_files returns Path objects."""
        mock_run.return_value = _mock_process(0, "staged.py\n")
        files = get_staged_files()
        self.assertEqual(len(files), 1)

    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    def test_run_diff_checks_no_files(self, mock_get: MagicMock) -> None:
        """Test diff with no changed files passes."""
        mock_get.return_value = []
        passed, output = run_diff_checks()
        self.assertTrue(passed)
        self.assertIn("No changed files", output)

    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    def test_run_pre_commit_no_files(self, mock_get: MagicMock) -> None:
        """Test pre-commit with no staged files passes."""
        mock_get.return_value = []
        passed, output = run_pre_commit_checks()
        self.assertTrue(passed)
        self.assertIn("No staged files", output)

    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    def test_run_diff_checks_with_py_files(
        self,
        mock_format: MagicMock,
        mock_lint: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        """Test diff checks with Python files."""
        # Create a real temp file so exists() returns True
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            tmp = Path(f.name)
        try:
            mock_get.return_value = [tmp]
            mock_lint.return_value = (True, "")
            mock_format.return_value = (True, "")
            passed, output = run_diff_checks()
            self.assertTrue(passed)
            self.assertIn("pass checks", output)
        finally:
            tmp.unlink(missing_ok=True)

    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    def test_run_diff_checks_non_code_files(self, mock_get: MagicMock) -> None:
        """Test diff skips non-code files."""
        mock_get.return_value = [Path("README.md"), Path("config.yml")]
        passed, output = run_diff_checks()
        self.assertTrue(passed)
        self.assertIn("No code files", output)


if __name__ == "__main__":
    unittest.main()
