"""External linter runner and result aggregation.

Runs ruff, mypy, eslint, golangci-lint and normalizes results
into a unified format. Extracted from validate_language_rules.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def run_linter_aggregation(
    dirpath: Path,
    linters: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run external linters and aggregate results into unified format.

    Supported linters: ruff, mypy, eslint, golangci-lint
    Returns list of unified issue dicts.
    """

    if linters is None:
        linters = []

    unified: list[dict[str, Any]] = []

    for linter in linters:
        if linter == "ruff":
            unified.extend(_run_ruff(dirpath))
        elif linter == "mypy":
            unified.extend(_run_mypy(dirpath))
        elif linter == "eslint":
            unified.extend(_run_eslint(dirpath))
        elif linter == "golangci-lint":
            unified.extend(_run_golangci(dirpath))

    return unified


def _run_ruff(dirpath: Path) -> list[dict[str, Any]]:
    """Run ruff and parse results."""
    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for item in data:
                issues.append(
                    {
                        "linter": "ruff",
                        "rule_id": item.get("code", ""),
                        "severity": "error" if item.get("fix") is None else "warning",
                        "file": item.get("filename", ""),
                        "line": item.get("location", {}).get("row", 0),
                        "message": item.get("message", ""),
                    }
                )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return issues


def _run_mypy(dirpath: Path) -> list[dict[str, Any]]:
    """Run mypy and parse results."""
    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            [
                "mypy",
                "--ignore-missing-imports",
                "--no-error-summary",
                "--show-error-codes",
                str(dirpath),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        for line in result.stdout.splitlines():
            if ": error:" in line:
                parts = line.split(": ", 2)
                if len(parts) >= 3:
                    file_line = parts[0]
                    msg = parts[1]
                    code = parts[2] if len(parts) > 2 else ""
                    fl = file_line.rsplit(":", 1)
                    issues.append(
                        {
                            "linter": "mypy",
                            "rule_id": code.strip("()"),
                            "severity": "error",
                            "file": fl[0] if len(fl) > 1 else str(dirpath),
                            "line": int(fl[1]) if fl[1].isdigit() else 0,
                            "message": msg,
                        }
                    )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return issues


def _run_eslint(dirpath: Path) -> list[dict[str, Any]]:
    """Run eslint and parse results."""
    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["eslint", "--format=json", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for file_entry in data:
                for msg in file_entry.get("messages", []):
                    issues.append(
                        {
                            "linter": "eslint",
                            "rule_id": msg.get("ruleId", ""),
                            "severity": ("error" if msg.get("severity") == 2 else "warning"),
                            "file": file_entry.get("filePath", ""),
                            "line": msg.get("line", 0),
                            "message": msg.get("message", ""),
                        }
                    )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return issues


def _run_golangci(dirpath: Path) -> list[dict[str, Any]]:
    """Run golangci-lint and parse results."""
    issues: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["golangci-lint", "run", "--out-format=json", str(dirpath)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for issue in data.get("Issues", []):
                issues.append(
                    {
                        "linter": "golangci-lint",
                        "rule_id": issue.get("FromLinter", ""),
                        "severity": "error",
                        "file": issue.get("Pos", {}).get("Filename", ""),
                        "line": issue.get("Pos", {}).get("Line", 0),
                        "message": issue.get("Text", ""),
                    }
                )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return issues
