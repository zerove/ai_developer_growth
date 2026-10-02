"""Tests for linter_runner.py (0% → target 80%)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.linter_runner import (
    _run_eslint,
    _run_golangci,
    _run_mypy,
    _run_ruff,
    run_linter_aggregation,
)


class TestRunLinterAggregation:
    """Tests for the main aggregation entry point."""

    def test_empty_linters(self, tmp_path: Path) -> None:
        """No linters specified returns empty list."""
        result = run_linter_aggregation(tmp_path)
        assert result == []

    def test_none_linters(self, tmp_path: Path) -> None:
        """None linters returns empty list."""
        result = run_linter_aggregation(tmp_path, linters=None)
        assert result == []

    @patch("tools.scripts.linter_runner._run_ruff")
    def test_single_linter(self, mock_ruff: MagicMock, tmp_path: Path) -> None:
        """Single linter calls the right function."""
        mock_ruff.return_value = [{"linter": "ruff", "rule_id": "E1"}]
        result = run_linter_aggregation(tmp_path, linters=["ruff"])
        assert len(result) == 1
        assert result[0]["linter"] == "ruff"
        mock_ruff.assert_called_once_with(tmp_path)

    @patch("tools.scripts.linter_runner._run_mypy")
    @patch("tools.scripts.linter_runner._run_ruff")
    def test_multiple_linters(self, mock_ruff: MagicMock, mock_mypy: MagicMock, tmp_path: Path) -> None:
        """Multiple linters aggregate results."""
        mock_ruff.return_value = [{"linter": "ruff"}]
        mock_mypy.return_value = [{"linter": "mypy"}, {"linter": "mypy"}]
        result = run_linter_aggregation(tmp_path, linters=["ruff", "mypy"])
        assert len(result) == 3

    def test_unknown_linter(self, tmp_path: Path) -> None:
        """Unknown linter name is silently ignored."""
        result = run_linter_aggregation(tmp_path, linters=["unknown-linter"])
        assert result == []

    @patch("tools.scripts.linter_runner._run_eslint")
    def test_eslint_called(self, mock_eslint: MagicMock, tmp_path: Path) -> None:
        """eslint linter is dispatched correctly."""
        mock_eslint.return_value = []
        run_linter_aggregation(tmp_path, linters=["eslint"])
        mock_eslint.assert_called_once()

    @patch("tools.scripts.linter_runner._run_golangci")
    def test_golangci_called(self, mock_go: MagicMock, tmp_path: Path) -> None:
        """golangci-lint is dispatched correctly."""
        mock_go.return_value = []
        run_linter_aggregation(tmp_path, linters=["golangci-lint"])
        mock_go.assert_called_once()


class TestRunRuff:
    """Tests for _run_ruff."""

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_ruff_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Ruff with JSON output parsed correctly."""
        ruff_output = [
            {
                "code": "E501",
                "message": "line too long",
                "filename": "test.py",
                "location": {"row": 10},
                "fix": None,
            },
            {
                "code": "W291",
                "message": "trailing whitespace",
                "filename": "test.py",
                "location": {"row": 5},
                "fix": {"applicability": "safe"},
            },
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(ruff_output), stderr="")
        issues = _run_ruff(tmp_path)
        assert len(issues) == 2
        assert issues[0]["linter"] == "ruff"
        assert issues[0]["rule_id"] == "E501"
        assert issues[0]["severity"] == "error"  # No fix
        assert issues[1]["severity"] == "warning"  # Has fix

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_ruff_empty_output(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Ruff with empty output returns empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        issues = _run_ruff(tmp_path)
        assert issues == []

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_ruff_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Ruff timeout 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ruff", timeout=60)
        issues = _run_ruff(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "ruff"
        assert issues[0]["rule_id"] == "ruff-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_ruff_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Ruff not found 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = FileNotFoundError
        issues = _run_ruff(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "ruff"
        assert issues[0]["rule_id"] == "ruff-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_ruff_invalid_json(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Ruff invalid json 视为门禁失败（fail-closed）。"""
        mock_run.return_value = MagicMock(returncode=1, stdout="not json", stderr="")
        issues = _run_ruff(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "ruff"
        assert issues[0]["rule_id"] == "ruff-unavailable"
        assert issues[0]["severity"] == "error"


class TestRunMypy:
    """Tests for _run_mypy."""

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_mypy_errors(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Mypy error lines parsed correctly."""
        mypy_output = (
            "test.py:10: error: Incompatible types [assignment]\nother.py:5: error: Missing return [return-value]\n"
        )
        mock_run.return_value = MagicMock(returncode=1, stdout=mypy_output, stderr="")
        issues = _run_mypy(tmp_path)
        assert len(issues) == 2
        assert issues[0]["linter"] == "mypy"
        assert issues[0]["file"] == "test.py"
        assert issues[0]["line"] == 10
        assert issues[0]["rule_id"] in ("assignment", "Incompatible types [assignment]")

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_mypy_clean(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Mypy with no errors returns empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Success: no issues found\n", stderr="")
        issues = _run_mypy(tmp_path)
        assert issues == []

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_mypy_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Mypy timeout 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="mypy", timeout=60)
        issues = _run_mypy(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "mypy"
        assert issues[0]["rule_id"] == "mypy-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_mypy_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Mypy not found 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = FileNotFoundError
        issues = _run_mypy(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "mypy"
        assert issues[0]["rule_id"] == "mypy-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_mypy_line_without_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Mypy non-error lines are ignored."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="test.py: note: In module imported here\nSuccess: no issues found\n",
            stderr="",
        )
        issues = _run_mypy(tmp_path)
        assert issues == []


class TestRunEslint:
    """Tests for _run_eslint."""

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_eslint_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Eslint JSON output parsed correctly."""
        eslint_output = [
            {
                "filePath": "test.js",
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "line": 5,
                        "message": "x is defined but never used",
                    },
                    {
                        "ruleId": "semi",
                        "severity": 1,
                        "line": 10,
                        "message": "Missing semicolon",
                    },
                ],
            }
        ]
        mock_run.return_value = MagicMock(returncode=1, stdout=json.dumps(eslint_output), stderr="")
        issues = _run_eslint(tmp_path)
        assert len(issues) == 2
        assert issues[0]["linter"] == "eslint"
        assert issues[0]["severity"] == "error"  # severity 2
        assert issues[1]["severity"] == "warning"  # severity 1

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_eslint_empty(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Eslint with empty output returns empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        issues = _run_eslint(tmp_path)
        assert issues == []

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_eslint_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Eslint timeout 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="eslint", timeout=60)
        issues = _run_eslint(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "eslint"
        assert issues[0]["rule_id"] == "eslint-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_eslint_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Eslint not found 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = FileNotFoundError
        issues = _run_eslint(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "eslint"
        assert issues[0]["rule_id"] == "eslint-unavailable"
        assert issues[0]["severity"] == "error"


class TestRunGolangci:
    """Tests for _run_golangci."""

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_golangci_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Golangci-lint output parsed correctly."""
        golangci_output = {
            "Issues": [
                {
                    "FromLinter": "govet",
                    "Pos": {"Filename": "main.go", "Line": 42},
                    "Text": "unused variable",
                }
            ]
        }
        mock_run.return_value = MagicMock(returncode=1, stdout=json.dumps(golangci_output), stderr="")
        issues = _run_golangci(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "golangci-lint"
        assert issues[0]["rule_id"] == "govet"
        assert issues[0]["file"] == "main.go"
        assert issues[0]["line"] == 42

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_golangci_empty(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Golangci-lint with empty output returns empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        issues = _run_golangci(tmp_path)
        assert issues == []

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_golangci_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Golangci timeout 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="golangci-lint", timeout=120)
        issues = _run_golangci(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "golangci-lint"
        assert issues[0]["rule_id"] == "golangci-lint-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_golangci_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Golangci not found 视为门禁失败（fail-closed）。"""
        mock_run.side_effect = FileNotFoundError
        issues = _run_golangci(tmp_path)
        assert len(issues) == 1
        assert issues[0]["linter"] == "golangci-lint"
        assert issues[0]["rule_id"] == "golangci-lint-unavailable"
        assert issues[0]["severity"] == "error"

    @patch("tools.scripts.linter_runner.subprocess.run")
    def test_golangci_no_issues_key(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Golangci-lint output without Issues key returns empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        issues = _run_golangci(tmp_path)
        assert issues == []
