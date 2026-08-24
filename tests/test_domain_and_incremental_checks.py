"""Tests for hooks/domain_checks.py (55% → target 85%) and hooks/incremental_checks.py (64% → target 85%)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.hooks.domain_checks import (
    run_governance_audit,
    run_language_rules,
    run_quality_gate,
)
from tools.scripts.hooks.incremental_checks import (
    _check_code_files,
    get_changed_files,
    get_staged_files,
    run_diff_checks,
    run_pre_commit_checks,
)
from tools.scripts.rules_engine.validators.models import ValidationResult

# ──────────────────────────────────────────────────────────
# domain_checks.py tests
# ──────────────────────────────────────────────────────────


class TestRunLanguageRules:
    @patch("tools.scripts.hooks.domain_checks.validate_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_file_valid(self, mock_detect: MagicMock, mock_validate: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# ok\n")
        mock_detect.return_value = "python"
        mock_validate.return_value = ValidationResult(file=str(f), language="python", issues=[])
        passed, output = run_language_rules(f)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.validate_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_file_invalid(self, mock_detect: MagicMock, mock_validate: MagicMock, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.validators.models import Issue

        f = tmp_path / "test.py"
        f.write_text("# bad\n")
        mock_detect.return_value = "python"
        issue = Issue(
            rule_id="test",
            severity="error",
            category="test",
            file=str(f),
            line=1,
            message="bad",
        )
        mock_validate.return_value = ValidationResult(file=str(f), language="python", issues=[issue])
        passed, output = run_language_rules(f)
        assert passed is False

    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.domain_checks.validate_file")
    def test_file_unknown_language(self, mock_validate: MagicMock, mock_detect: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.touch()
        mock_detect.return_value = None
        passed, output = run_language_rules(f)
        assert passed is False
        assert "Cannot detect language" in output

    @patch("tools.scripts.hooks.domain_checks.validate_directory")
    def test_directory(self, mock_validate_dir: MagicMock) -> None:
        mock_validate_dir.return_value = [
            ValidationResult(file="a.py", language="python", issues=[]),
            ValidationResult(file="b.py", language="python", issues=[]),
        ]
        passed, output = run_language_rules(Path("/some/dir"))
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.validate_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_file_with_lang_override(self, mock_detect: MagicMock, mock_validate: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# ok\n")
        mock_detect.return_value = "typescript"  # Would return ts if detected
        mock_validate.return_value = ValidationResult(file=str(f), language="python", issues=[])
        passed, output = run_language_rules(f, lang="python")
        # lang override bypasses detect_language_from_file
        mock_detect.assert_not_called()


class TestRunQualityGate:
    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_file_check(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# test\n")
        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}
        passed, output = run_quality_gate(f, check_annotation=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_full_checks(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# test\n")
        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}
        passed, output = run_quality_gate(f, full=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_json_format(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# test\n")
        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}
        passed, output = run_quality_gate(f, format="json")
        data = json.loads(output)
        assert "summary" in data

    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_no_files(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        passed, output = run_quality_gate(tmp_path / "nonexistent_dir")
        assert passed is True
        assert "No files" in output

    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_failed_checks(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# bad\n")
        mock_detect.return_value = "python"
        mock_check.return_value = {
            "passed": False,
            "issues": [{"line": 1, "type": "error", "message": "bad"}],
        }
        passed, output = run_quality_gate(f, check_security=True)
        assert passed is False

    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_check_patterns(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# test\n")
        mock_detect.return_value = "python"
        mock_check.return_value = {"passed": True, "issues": []}
        passed, _ = run_quality_gate(f, check_patterns=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.check_file")
    @patch("tools.scripts.hooks.domain_checks.detect_language_from_file")
    def test_many_issues_truncation(self, mock_detect: MagicMock, mock_check: MagicMock, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# test\n")
        mock_detect.return_value = "python"
        issues = [{"line": i, "type": "error", "message": f"issue {i}"} for i in range(10)]
        mock_check.return_value = {"passed": False, "issues": issues}
        passed, output = run_quality_gate(f)
        assert "more" in output


class TestRunGovernanceAudit:
    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_full(self, mock_load: MagicMock) -> None:
        ga = MagicMock()
        ga.lint.return_value = True
        ga.format_check.return_value = True
        ga.typecheck.return_value = True
        ga.test.return_value = True
        ga.validate_governance_docs.return_value = True
        ga.check_ai_sdlc_compliance.return_value = True
        ga.audit_hallucination_risks.return_value = True
        mock_load.return_value = ga
        passed, output = run_governance_audit(full=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_validate_docs(self, mock_load: MagicMock) -> None:
        ga = MagicMock()
        ga.validate_governance_docs.return_value = True
        mock_load.return_value = ga
        passed, output = run_governance_audit(validate_docs=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_check_ai_sdlc(self, mock_load: MagicMock) -> None:
        ga = MagicMock()
        ga.check_ai_sdlc_compliance.return_value = False
        mock_load.return_value = ga
        passed, output = run_governance_audit(check_ai_sdlc=True)
        assert passed is False
        assert "AI-SDLC" in output

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_audit_hallucination(self, mock_load: MagicMock) -> None:
        ga = MagicMock()
        ga.audit_hallucination_risks.return_value = True
        mock_load.return_value = ga
        passed, _ = run_governance_audit(audit_hallucination=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks.subprocess.run")
    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_check_index(self, mock_load: MagicMock, mock_run: MagicMock) -> None:
        ga = MagicMock()
        mock_load.return_value = ga
        mock_run.return_value = MagicMock(returncode=0)
        passed, _ = run_governance_audit(check_index=True)
        assert passed is True

    @patch("tools.scripts.hooks.domain_checks._load_governance_auditor")
    def test_no_checks_uses_default(self, mock_load: MagicMock) -> None:
        ga = MagicMock()
        ga.lint.return_value = True
        ga.format_check.return_value = True
        ga.typecheck.return_value = True
        ga.test.return_value = True
        ga.validate_governance_docs.return_value = True
        ga.check_ai_sdlc_compliance.return_value = True
        mock_load.return_value = ga
        passed, _ = run_governance_audit()
        assert passed is True


# ──────────────────────────────────────────────────────────
# incremental_checks.py tests
# ──────────────────────────────────────────────────────────


class TestGetChangedFiles:
    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="a.py\nb.rs\n", stderr="")
        files = get_changed_files("HEAD")
        assert len(files) == 2

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_fallback(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=128, stdout=""),
            MagicMock(returncode=0, stdout="fallback.py\n"),
        ]
        files = get_changed_files("bad-ref")
        assert len(files) == 1

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
        files = get_changed_files()
        assert files == []


class TestGetStagedFiles:
    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="staged.py\n", stderr="")
        files = get_staged_files()
        assert len(files) == 1

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
        assert get_staged_files() == []


class TestCheckCodeFiles:
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    def test_all_pass(
        self,
        mock_lint: MagicMock,
        mock_fmt: MagicMock,
        mock_detect: MagicMock,
        mock_validate: MagicMock,
    ) -> None:
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (True, "")
        mock_detect.return_value = "python"
        mock_validate.return_value = ValidationResult(file="test.py", language="python", issues=[])
        passed, output = _check_code_files([Path("test.py")], label="Test")
        assert passed is True

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    def test_empty_files(self, mock_lint: MagicMock) -> None:
        passed, output = _check_code_files([], label="Empty")
        assert passed is True

    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    def test_lint_fails(
        self,
        mock_lint: MagicMock,
        mock_fmt: MagicMock,
        mock_detect: MagicMock,
        mock_validate: MagicMock,
    ) -> None:
        mock_lint.return_value = (False, "lint error")
        mock_fmt.return_value = (True, "")
        mock_detect.return_value = "python"
        mock_validate.return_value = ValidationResult(file="test.py", language="python", issues=[])
        passed, output = _check_code_files([Path("test.py")], label="Test")
        assert passed is False
        assert "Lint errors" in output


class TestRunDiffChecks:
    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    def test_no_changes(self, mock_get: MagicMock) -> None:
        mock_get.return_value = []
        passed, output = run_diff_checks()
        assert passed is True
        assert "No changed files" in output

    @patch("tools.scripts.hooks.incremental_checks._check_code_files")
    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    def test_no_code_files(self, mock_get: MagicMock, mock_check: MagicMock) -> None:
        mock_get.return_value = [Path("readme.md")]
        passed, output = run_diff_checks()
        assert passed is True
        assert "No code files" in output


class TestRunPreCommitChecks:
    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    def test_no_staged(self, mock_get: MagicMock) -> None:
        mock_get.return_value = []
        passed, output = run_pre_commit_checks()
        assert passed is True
        assert "No staged files" in output
