# 拆分自 tests/test_adg_cli_v2.py

"""Phase 27: Comprehensive tests for adg_cli.py (43% -> 80%)."""

from __future__ import annotations

import json

from tools.scripts.adg_cli import (
    Issue,
    _format_human,
    _format_json,
)


class TestFormatHuman:
    def test_with_issues(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "f.py", 1, 1, "msg1", "fix1"),
            Issue("r2", "warning", "style", "f.py", 2, 1, "msg2", ""),
        ]
        output = _format_human(issues, "python", "django", 3)
        assert "python" in output
        assert "django" in output
        assert "msg1" in output
        assert "error" in output
        assert "warning" in output

    def test_no_issues(self) -> None:
        output = _format_human([], "python", None, 5)
        assert "All checks passed" in output
        assert "5 files" in output

    def test_with_framework_none(self) -> None:
        output = _format_human([], "rust", None, 1)
        assert "N/A" not in output

    def test_fix_hint_displayed(self) -> None:
        issues = [Issue("r1", "error", "sec", "f.py", 1, 1, "msg", "use safe")]
        output = _format_human(issues, "python", None, 1)
        assert "use safe" in output

    def test_single_file(self) -> None:
        output = _format_human([], "python", None, 1)
        assert "1 file" in output

    def test_info_severity(self) -> None:
        issues = [Issue("r1", "info", "style", "f.py", 1, 1, "msg", "")]
        output = _format_human(issues, "python", None, 1)
        assert "info" in output

    def test_grouping_by_file(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "a.py", 1, 1, "msg1", ""),
            Issue("r2", "error", "sec", "b.py", 1, 1, "msg2", ""),
        ]
        output = _format_human(issues, "python", None, 2)
        assert "a.py" in output
        assert "b.py" in output


class TestFormatJson:
    def test_with_issues(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "f.py", 1, 1, "msg1", "fix1"),
            Issue("r2", "warning", "style", "f.py", 2, 1, "msg2", ""),
        ]
        output = _format_json(issues, "python", "django", 3)
        data = json.loads(output)
        assert data["language"] == "python"
        assert data["framework"] == "django"
        assert data["files_checked"] == 3
        assert data["summary"]["error"] == 1
        assert data["summary"]["warning"] == 1

    def test_no_issues(self) -> None:
        output = _format_json([], "rust", None, 5)
        data = json.loads(output)
        assert data["summary"] == {"error": 0, "warning": 0, "info": 0}
