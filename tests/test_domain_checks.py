"""Tests for domain_checks hook module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks.domain_checks import (
    run_arch_graph,
    run_governance_audit,
    run_language_rules,
    run_pr_review,
    run_quality_gate,
)


class TestRunLanguageRules:
    """Tests for run_language_rules function."""

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.validate_file")
    def test_run_language_rules_file_pass(
        self, mock_validate, mock_detect, tmp_path: Path
    ):
        """Test language rules on a passing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_detect.return_value = "python"
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.issues = []
        mock_result.to_dict.return_value = {"passed": True, "issues": []}
        mock_validate.return_value = mock_result

        passed, output = run_language_rules(test_file)
        assert passed is True
        assert "PASS" in output or "passed" in output.lower()

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.validate_file")
    def test_run_language_rules_file_fail(
        self, mock_validate, mock_detect, tmp_path: Path
    ):
        """Test language rules on a failing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_detect.return_value = "python"
        mock_result = MagicMock()
        mock_result.passed = False
        mock_result.issues = [MagicMock(line=1, type="error", message="test issue")]
        mock_result.to_dict.return_value = {
            "passed": False,
            "issues": [{"line": 1, "type": "error", "message": "test issue"}],
        }
        mock_validate.return_value = mock_result

        passed, output = run_language_rules(test_file)
        assert passed is False
        # Output is JSON dict string, contains "false" (lowercase)
        assert "false" in output.lower()

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.validate_file")
    def test_run_language_rules_unknown_lang(
        self, mock_validate, mock_detect, tmp_path: Path
    ):
        """Test language rules with unknown language."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("unknown")

        mock_detect.return_value = None

        passed, output = run_language_rules(test_file)
        assert passed is False
        assert "Cannot detect language" in output

    @patch("tools.scripts.hooks.domain_checks.validate_directory")
    def test_run_language_rules_directory(self, mock_validate, tmp_path: Path):
        """Test language rules on directory."""
        mock_validate.return_value = [
            MagicMock(file="test1.py", passed=True, issues=[]),
            MagicMock(file="test2.py", passed=False, issues=[MagicMock()]),
        ]

        passed, output = run_language_rules(tmp_path)
        assert passed is False  # One failed
        assert "test1.py" in output
        assert "test2.py" in output


class TestRunQualityGate:
    """Tests for run_quality_gate function."""

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.check_file")
    def test_run_quality_gate_file_pass(self, mock_check, mock_detect, tmp_path: Path):
        """Test quality gate on a passing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): return 1")

        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}

        passed, output = run_quality_gate(test_file)
        assert passed is True
        assert "✅" in output or "passed" in output.lower()

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.check_file")
    def test_run_quality_gate_file_fail(self, mock_check, mock_detect, tmp_path: Path):
        """Test quality gate on a failing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): return 1")

        mock_detect.return_value = "python"
        mock_check.return_value = {
            "passed": False,
            "issues": [{"line": 1, "type": "error", "message": "test"}],
        }

        passed, output = run_quality_gate(test_file)
        assert passed is False
        assert "❌" in output

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.check_file")
    def test_run_quality_gate_directory(self, mock_check, mock_detect, tmp_path: Path):
        """Test quality gate on directory."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): return 1")

        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}

        passed, output = run_quality_gate(tmp_path)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.check_file")
    def test_run_quality_gate_json_format(
        self, mock_check, mock_detect, tmp_path: Path
    ):
        """Test quality gate with JSON output."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): return 1")

        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}

        passed, output = run_quality_gate(test_file, format="json")
        assert passed is True
        data = json.loads(output)
        assert "summary" in data
        assert "results" in data

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.check_file")
    def test_run_quality_gate_skips_test_files(
        self, mock_check, mock_detect, tmp_path: Path
    ):
        """Test quality gate skips certain checks for test files."""
        test_file = tmp_path / "tests" / "test_file.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_foo(): assert True")

        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}

        passed, output = run_quality_gate(test_file, check_patterns=True)
        assert passed is True
        # Should only run annotation check for test files
        mock_check.assert_called_once()
        call_args = mock_check.call_args
        # check_file(filepath, checks) - second positional arg is checks
        assert call_args[0][1] == ["annotation"]


class TestRunGovernanceAudit:
    """Tests for run_governance_audit function."""

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_run_governance_audit_full(self, mock_load):
        """Test full governance audit."""
        mock_ga = MagicMock()
        mock_ga.lint.return_value = True
        mock_ga.format_check.return_value = True
        mock_ga.typecheck.return_value = True
        mock_ga.test.return_value = True
        mock_ga.validate_governance_docs.return_value = True
        mock_ga.check_ai_sdlc_compliance.return_value = True
        mock_load.return_value = mock_ga

        passed, output = run_governance_audit(full=True)
        assert passed is True
        assert "PASS" in output

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_run_governance_audit_specific_checks(self, mock_load):
        """Test governance audit with specific checks."""
        mock_ga = MagicMock()
        mock_ga.validate_governance_docs.return_value = True
        mock_ga.check_ai_sdlc_compliance.return_value = True
        mock_load.return_value = mock_ga

        passed, output = run_governance_audit(validate_docs=True, check_ai_sdlc=True)
        assert passed is True
        mock_ga.validate_governance_docs.assert_called_once()
        mock_ga.check_ai_sdlc_compliance.assert_called_once()

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_run_governance_audit_failure(self, mock_load):
        """Test governance audit with failures."""
        mock_ga = MagicMock()
        mock_ga.lint.return_value = False
        mock_ga.format_check.return_value = True
        mock_ga.typecheck.return_value = True
        mock_ga.test.return_value = True
        mock_load.return_value = mock_ga

        passed, output = run_governance_audit(full=True)
        assert passed is False
        assert "FAIL" in output
        assert "Lint" in output

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_run_governance_audit_check_index(self, mock_load):
        """Test governance audit with check_index."""
        mock_ga = MagicMock()
        mock_load.return_value = mock_ga

        with patch("tools.scripts.hooks.domain_checks.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            passed, output = run_governance_audit(check_index=True)
            assert passed is True

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_run_governance_audit_import_error(self, mock_load):
        """Test governance audit with import error."""
        mock_load.side_effect = ImportError("Failed to load")

        # The function will raise ImportError, let's see what happens
        try:
            run_governance_audit(full=True)
            assert False, "Should have raised ImportError"
        except ImportError:
            pass  # Expected


class TestRunPrReview:
    """Tests for run_pr_review function."""

    @patch("tools.scripts.ai_pr_reviewer.get_git_diff")
    @patch("tools.scripts.ai_pr_reviewer.review_diff")
    @patch("tools.scripts.ai_pr_reviewer.format_review_report")
    def test_run_pr_review_pass(self, mock_format, mock_review, mock_diff):
        """Test PR review passes."""
        mock_diff.return_value = "diff content"
        mock_review.return_value = {"total_findings": 0}
        mock_format.return_value = "Report"

        passed, output = run_pr_review()
        assert passed is True
        assert output == "Report"

    @patch("tools.scripts.ai_pr_reviewer.get_git_diff")
    @patch("tools.scripts.ai_pr_reviewer.review_diff")
    @patch("tools.scripts.ai_pr_reviewer.format_review_report")
    def test_run_pr_review_fail(self, mock_format, mock_review, mock_diff):
        """Test PR review fails."""
        mock_diff.return_value = "diff content"
        mock_review.return_value = {"total_findings": 3}
        mock_format.return_value = "Report with findings"

        passed, output = run_pr_review()
        assert passed is False
        assert "Report with findings" in output


class TestRunArchGraph:
    """Tests for run_arch_graph function."""

    @patch("tools.scripts.arch_visualizer.scan_python_imports")
    @patch("tools.scripts.arch_visualizer.generate_mermaid_diagram")
    def test_run_arch_graph(self, mock_generate, mock_scan):
        """Test architecture graph generation."""
        mock_scan.return_value = {"module1": ["module2"], "module2": []}
        mock_generate.return_value = "graph TD\n  A --> B"

        passed, output = run_arch_graph()
        assert passed is True
        assert "Architecture graph generated" in output
        assert "mermaid" in output
        assert "2 modules mapped" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
