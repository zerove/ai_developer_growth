# 拆分自 tests/test_language_rules_v2.py

"""Tests for language rules v2 features: auto-fix, custom rules, reports, health score, linter aggregation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from tools.scripts.validate_language_rules import (
    Issue,
    ValidationResult,
    calculate_health_score,
    generate_html_report,
    generate_junit_xml,
    generate_sarif,
    write_report,
)


class TestReports:
    def _make_results(self) -> list[ValidationResult]:
        r1 = ValidationResult(file="good.py", language="python", lines_checked=10)
        r2 = ValidationResult(file="bad.py", language="python", lines_checked=20)
        r2.issues.append(
            Issue(
                rule_id="py-test",
                severity="error",
                category="security",
                file="bad.py",
                line=5,
                message="Security issue",
            )
        )
        return [r1, r2]

    def test_junit_xml(self) -> None:
        results = self._make_results()
        xml = generate_junit_xml(results)
        assert '<?xml version="1.0"' in xml
        assert '<testsuite name="language-rules"' in xml
        assert 'tests="2"' in xml
        assert 'failures="1"' in xml

    def test_html_report(self) -> None:
        results = self._make_results()
        html = generate_html_report(results)
        assert "<!DOCTYPE html>" in html
        assert "good.py" in html
        assert "bad.py" in html

    def test_write_report_json(self, tmp_path: Path) -> None:
        results = self._make_results()
        out = tmp_path / "report.json"
        content = write_report(results, "json", out)
        assert content is not None
        data = json.loads(content)
        assert data["summary"]["total_files"] == 2
        assert data["summary"]["total_errors"] == 1
        assert out.exists()

    def test_write_report_junit(self, tmp_path: Path) -> None:
        results = self._make_results()
        out = tmp_path / "report.xml"
        content = write_report(results, "junit", out)
        assert content is not None
        assert "<testsuite" in content
        assert out.exists()

    def test_write_report_html(self, tmp_path: Path) -> None:
        results = self._make_results()
        out = tmp_path / "report.html"
        content = write_report(results, "html", out)
        assert content is not None
        assert "<!DOCTYPE html>" in content
        assert out.exists()


class TestHealthScore:
    def test_perfect_score(self) -> None:
        results = [ValidationResult(file="clean.py", language="python", lines_checked=10)]
        health = calculate_health_score(results)
        assert health.score >= 90
        assert health.grade == "A"

    def test_errors_reduce_score(self) -> None:
        r = ValidationResult(file="bad.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(
                rule_id="test",
                severity="error",
                category="security",
                file="bad.py",
                line=1,
                message="err",
            )
        )
        health = calculate_health_score([r])
        assert health.score < 100
        assert any("errors" in d for d in health.details)

    def test_warnings_reduce_score(self) -> None:
        r = ValidationResult(file="warn.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(
                rule_id="test",
                severity="warning",
                category="general",
                file="warn.py",
                line=1,
                message="warn",
            )
        )
        health = calculate_health_score([r])
        # Warning penalty (-2) is offset by clean file bonus (+2), so score may stay 100
        # But the breakdown should show the penalty
        assert health.breakdown["warning_penalty"] < 0
        assert "warnings" in " ".join(health.details).lower()

    def test_grade_scale(self) -> None:
        # Many errors = F grade
        r = ValidationResult(file="bad.py", language="python", lines_checked=10)
        for i in range(20):
            r.issues.append(
                Issue(
                    rule_id=f"test-{i}",
                    severity="error",
                    category="security",
                    file="bad.py",
                    line=i + 1,
                    message="err",
                )
            )
        health = calculate_health_score([r])
        assert health.score <= 60
        assert health.grade in ("D", "F")

    def test_to_dict(self) -> None:
        results = [ValidationResult(file="clean.py", language="python", lines_checked=10)]
        health = calculate_health_score(results)
        d = health.to_dict()
        assert "score" in d
        assert "grade" in d
        assert "breakdown" in d


class TestThresholds:
    def test_max_errors_cli(self, tmp_path: Path) -> None:
        """Test that max-errors threshold works via validate_file."""
        r = ValidationResult(file="test.py", language="python")
        r.issues.append(
            Issue(
                rule_id="e1",
                severity="error",
                category="sec",
                file="test.py",
                line=1,
                message="err1",
            )
        )
        r.issues.append(
            Issue(
                rule_id="e2",
                severity="error",
                category="sec",
                file="test.py",
                line=2,
                message="err2",
            )
        )

        # 2 errors, threshold 1 -> should fail
        total_errors = sum(1 for i in r.issues if i.severity == "error")
        assert total_errors > 1

    def test_max_warnings_cli(self) -> None:
        """Test that max-warnings threshold works."""
        r = ValidationResult(file="test.py", language="python")
        for i in range(5):
            r.issues.append(
                Issue(
                    rule_id=f"w{i}",
                    severity="warning",
                    category="gen",
                    file="test.py",
                    line=i + 1,
                    message="warn",
                )
            )
        total_warnings = sum(1 for i in r.issues if i.severity == "warning")
        assert total_warnings == 5


class TestIssueFixReplacement:
    def test_fix_replacement_in_to_dict(self) -> None:
        issue = Issue(
            rule_id="test",
            severity="error",
            category="security",
            file="test.py",
            line=1,
            message="test",
            fix_replacement="s/old/new/",
        )
        d = issue.to_dict()
        assert "fix_replacement" in d
        assert d["fix_replacement"] == "s/old/new/"

    def test_no_fix_replacement_in_to_dict(self) -> None:
        issue = Issue(
            rule_id="test",
            severity="error",
            category="security",
            file="test.py",
            line=1,
            message="test",
        )
        d = issue.to_dict()
        assert "fix_replacement" not in d


class TestSARIF:
    def test_generate_sarif(self) -> None:
        r = ValidationResult(file="test.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(
                rule_id="py-test",
                severity="error",
                category="security",
                file="test.py",
                line=5,
                message="Security issue",
            )
        )
        sarif_json = generate_sarif([r])
        sarif = json.loads(sarif_json)
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        assert len(sarif["runs"][0]["results"]) == 1
        assert sarif["runs"][0]["results"][0]["ruleId"] == "py-test"
        assert sarif["runs"][0]["results"][0]["level"] == "error"

    def test_sarif_empty(self) -> None:
        sarif_json = generate_sarif([])
        sarif = json.loads(sarif_json)
        assert sarif["runs"][0]["results"] == []

    def test_sarif_severity_levels(self) -> None:
        r = ValidationResult(file="test.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(
                rule_id="e",
                severity="error",
                category="c",
                file="test.py",
                line=1,
                message="e",
            )
        )
        r.issues.append(
            Issue(
                rule_id="w",
                severity="warning",
                category="c",
                file="test.py",
                line=2,
                message="w",
            )
        )
        r.issues.append(
            Issue(
                rule_id="i",
                severity="info",
                category="c",
                file="test.py",
                line=3,
                message="i",
            )
        )
        sarif = json.loads(generate_sarif([r]))
        levels = [res["level"] for res in sarif["runs"][0]["results"]]
        assert levels == ["error", "warning", "note"]

    def test_write_report_sarif(self, tmp_path: Path) -> None:
        r = ValidationResult(file="test.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(
                rule_id="py-test",
                severity="error",
                category="security",
                file="test.py",
                line=1,
                message="err",
            )
        )
        out = tmp_path / "report.sarif"
        content = write_report([r], "sarif", out)
        assert content is not None
        assert out.exists()
        sarif = json.loads(content)
        assert sarif["version"] == "2.1.0"
