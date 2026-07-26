"""Coverage sprint tests for low-coverage modules.

Targets:
- create_case_study.py (77% -> 95%+)
- rule_engine.py (80% -> 95%+)
- fix_metadata.py (81% -> 95%+)
- rule_catalog.py (86% -> 95%+)
- hooks/incremental_checks.py (82% -> 95%+)
- report_generator.py (89% -> 95%+)
- contributor_dashboard.py (87% -> 95%+)
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# ──────────────────────────────────────────────────────────
# create_case_study.py
# ──────────────────────────────────────────────────────────


class TestCreateCaseStudy:
    def test_create_with_existing_template(self, tmp_path: Path) -> None:
        from tools.scripts.create_case_study import create_case_study_structure

        # Create a template file
        tpl_dir = tmp_path / "templates"
        tpl_dir.mkdir()
        tpl_file = tpl_dir / "case-study-template.md"
        tpl_file.write_text("# [简短标题] - template\n2026-07-21")

        base = tmp_path / "cases"
        base.mkdir()
        result = create_case_study_structure("Test Case", base)
        assert result.exists()
        assert (result / "README.md").exists()
        assert (result / "docs" / "PRD.md").exists()
        assert (result / "docs" / "DESIGN.md").exists()
        assert (result / "docs" / "RETROSPECTIVE.md").exists()
        assert (result / "code" / ".gitkeep").exists()
        assert (result / "tests" / ".gitkeep").exists()
        assert (result / "assets" / ".gitkeep").exists()

    def test_get_default_template(self) -> None:
        from tools.scripts.create_case_study import get_default_template

        tpl = get_default_template()
        assert "案例" in tpl
        assert "背景" in tpl
        assert "效率对比" in tpl

    def test_main(self, tmp_path: Path) -> None:
        from tools.scripts.create_case_study import main

        base = tmp_path / "cases"
        with patch("sys.argv", ["prog", "My Test", "--dir", str(base)]):
            main()
        assert (base / "my-test").exists()


# ──────────────────────────────────────────────────────────
# rule_engine.py
# ──────────────────────────────────────────────────────────


class TestRuleEngine:
    def test_asdict_dataclass(self) -> None:
        from dataclasses import dataclass

        from tools.scripts.rule_engine import asdict

        @dataclass
        class Obj:
            x: int
            y: str

        assert asdict(Obj(1, "hi")) == {"x": 1, "y": "hi"}

    def test_asdict_dict(self) -> None:
        from tools.scripts.rule_engine import asdict

        assert asdict({"a": 1}) == {"a": 1}

    def test_asdict_other(self) -> None:
        from tools.scripts.rule_engine import asdict

        assert asdict(42) == {"value": 42}

    def test_validate_file(self, tmp_path: Path) -> None:
        from tools.scripts.rule_engine import RuleEngine

        py_file = tmp_path / "test.py"
        py_file.write_text("x = 1\n")

        engine = RuleEngine()
        result = engine.validate_file(str(py_file), "python")
        assert "file" in result
        assert result["language"] == "python"
        assert "issues" in result

    def test_validate_directory(self, tmp_path: Path) -> None:
        from tools.scripts.rule_engine import RuleEngine

        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")

        engine = RuleEngine()
        result = engine.validate_directory(str(tmp_path), "python")
        assert "results" in result
        assert "summary" in result
        assert result["summary"]["total_files"] >= 0

    def test_search_packs(self) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        results = engine.search_packs("security")
        assert isinstance(results, list)

    def test_get_pack_info(self) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        info = engine.get_pack_info("security")
        assert info is not None
        assert info["name"] == "Security Rules"

    def test_get_pack_info_unknown(self) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        assert engine.get_pack_info("nonexistent") is None

    def test_install_pack_dry_run(self, tmp_path: Path) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        result = engine.install_pack("security", tmp_path, dry_run=True)
        assert result == []

    def test_list_packs(self) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        packs = engine.list_packs()
        assert len(packs) > 0
        assert any(p["id"] == "security" for p in packs)

    def test_get_tracking_report_empty(self, tmp_path: Path) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        with patch("tools.scripts.rule_tracker._load_records", return_value=[]):
            report = engine.get_tracking_report()
            assert report["records"] == 0

    def test_get_tracking_report_with_data(self) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        mock_records = [
            {"summary": {"total_issues": 5, "by_rule": {"rule-a": 3, "rule-b": 2}}},
            {"summary": {"total_issues": 3, "by_rule": {"rule-a": 1, "rule-c": 2}}},
        ]
        with patch("tools.scripts.rule_tracker._load_records", return_value=mock_records):
            report = engine.get_tracking_report(days=7)
            assert report["records"] == 2
            assert report["total_issues"] == 8

    def test_record_results(self, tmp_path: Path) -> None:
        from tools.scripts.rule_engine import RuleEngine

        engine = RuleEngine()
        records_file = tmp_path / "records.jsonl"
        results = {
            "results": [{"file": "test.py", "issues": [{"severity": "error"}]}],
            "health_score": 85,
        }
        with patch("tools.scripts.rule_tracker._records_file", return_value=str(records_file)):
            engine.record_results(results, project="test-project")
        assert records_file.exists()
        content = records_file.read_text()
        data = json.loads(content.strip())
        assert data["project"] == "test-project"


# ──────────────────────────────────────────────────────────
# fix_metadata.py
# ──────────────────────────────────────────────────────────


class TestFixMetadata:
    def test_get_category_from_path(self) -> None:
        from tools.scripts.fix_metadata import get_category_from_path

        cat, tags = get_category_from_path("docs/efficiency/foo.md")
        assert cat == "效率层"
        assert "AI效率" in tags

    def test_get_category_unknown(self) -> None:
        from tools.scripts.fix_metadata import get_category_from_path

        cat, tags = get_category_from_path("random/foo.md")
        assert cat == "效率层"
        assert "AI开发" in tags

    def test_infer_title_from_content(self) -> None:
        from tools.scripts.fix_metadata import infer_title_from_content

        title = infer_title_from_content("# Hello World\n\nSome content", "foo.md")
        assert title == "Hello World"

    def test_infer_title_from_filename(self) -> None:
        from tools.scripts.fix_metadata import infer_title_from_content

        title = infer_title_from_content("no title here", "my-cool-file.md")
        assert title == "My Cool File"

    def test_infer_difficulty_advanced(self) -> None:
        from tools.scripts.fix_metadata import infer_difficulty

        assert infer_difficulty("This is an advanced topic") == "高级"

    def test_infer_difficulty_intermediate(self) -> None:
        from tools.scripts.fix_metadata import infer_difficulty

        assert infer_difficulty("中级教程") == "中级"

    def test_infer_difficulty_basic(self) -> None:
        from tools.scripts.fix_metadata import infer_difficulty

        assert infer_difficulty("simple intro") == "初级"

    def test_infer_tags(self) -> None:
        from tools.scripts.fix_metadata import infer_tags

        tags = infer_tags("python and docker tutorial", "python-docker.md")
        assert "Python" in tags
        assert "Docker" in tags

    def test_infer_tags_fallback(self) -> None:
        from tools.scripts.fix_metadata import infer_tags

        tags = infer_tags("nothing relevant", "foo.md")
        assert tags == ["技术文档"]

    def test_process_file_already_complete(self, tmp_path: Path) -> None:
        from tools.scripts.fix_metadata import process_file

        f = tmp_path / "done.md"
        f.write_text("---\ntitle: T\ndescription: D\ncategory: C\ntags: [t]\ndifficulty: 初级\n---\n\nContent")
        assert process_file(str(f)) is False

    def test_process_file_no_frontmatter(self, tmp_path: Path) -> None:
        from tools.scripts.fix_metadata import process_file

        f = tmp_path / "new.md"
        f.write_text("# Title\n\nContent here")
        assert process_file(str(f)) is True
        content = f.read_text()
        assert content.startswith("---")

    def test_process_file_incomplete_frontmatter(self, tmp_path: Path) -> None:
        from tools.scripts.fix_metadata import process_file

        f = tmp_path / "partial.md"
        f.write_text("---\ntitle: T\n---\n\nContent")
        assert process_file(str(f)) is True

    def test_generate_metadata(self, tmp_path: Path) -> None:
        from tools.scripts.fix_metadata import generate_metadata

        f = tmp_path / "test.md"
        f.write_text("# Test Doc\n\nDescription here\n\n## Section")
        meta = generate_metadata(str(f))
        assert "title:" in meta
        assert "category:" in meta

    def test_generate_metadata_no_desc(self, tmp_path: Path) -> None:
        from tools.scripts.fix_metadata import generate_metadata

        f = tmp_path / "bare.md"
        f.write_text("Just some text without title or description")
        meta = generate_metadata(str(f))
        assert "技术文档" in meta


# ──────────────────────────────────────────────────────────
# rule_catalog.py
# ──────────────────────────────────────────────────────────


class TestRuleCatalog:
    def test_validate_rules_not_found(self) -> None:
        from tools.scripts.rule_catalog import validate_rules

        total, errors, msgs = validate_rules(Path("/nonexistent"))
        assert total == 0
        assert "not found" in msgs[0].lower()

    def test_validate_rules_empty_yaml(self, tmp_path: Path) -> None:
        from tools.scripts.rule_catalog import validate_rules

        yml = tmp_path / "empty.yml"
        yml.write_text("")
        total, errors, msgs = validate_rules(tmp_path)
        assert errors >= 1

    def test_validate_rules_missing_fields(self, tmp_path: Path) -> None:
        from tools.scripts.rule_catalog import validate_rules

        yml = tmp_path / "bad.yml"
        yml.write_text("anti_patterns:\n  - id: test-rule\n")
        total, errors, msgs = validate_rules(tmp_path)
        assert errors >= 1
        assert any("pattern" in m for m in msgs)

    def test_validate_rules_yaml_parse_error(self, tmp_path: Path) -> None:
        from tools.scripts.rule_catalog import validate_rules

        yml = tmp_path / "bad_yaml.yml"
        yml.write_text("anti_patterns:\n  - {{{invalid yaml\n")
        total, errors, msgs = validate_rules(tmp_path)
        assert errors >= 1

    def test_export_rules(self, tmp_path: Path) -> None:
        from tools.scripts.rule_catalog import export_rules

        yml = tmp_path / "rules.yml"
        yml.write_text("anti_patterns:\n  - id: r1\n    pattern: test\n    message: msg\n")
        total, combined = export_rules(tmp_path, tmp_path / "out.yml")
        assert total >= 1
        assert len(combined["anti_patterns"]) >= 1

    def test_matches(self) -> None:
        from tools.scripts.rule_catalog import matches

        rule = {"id": "py-eval", "message": "eval usage", "pattern": r"\beval\b", "category": "security"}
        assert matches(rule, "eval") is True
        assert matches(rule, "nope") is False

    def test_get_pack_source(self) -> None:
        from tools.scripts.rule_catalog import get_pack_source

        path = get_pack_source("security")
        assert path is not None
        assert path.exists()

    def test_get_pack_source_unknown(self) -> None:
        from tools.scripts.rule_catalog import get_pack_source

        assert get_pack_source("nonexistent") is None

    def test_install_pack_unknown(self, tmp_path: Path) -> None:
        from tools.scripts.rule_catalog import install_pack

        with pytest.raises(ValueError, match="Unknown pack"):
            install_pack("nonexistent", tmp_path)


# ──────────────────────────────────────────────────────────
# hooks/incremental_checks.py
# ──────────────────────────────────────────────────────────


class TestIncrementalChecks:
    def test_get_changed_files_timeout(self) -> None:
        from tools.scripts.hooks.incremental_checks import get_changed_files

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            result = get_changed_files()
            assert result == []

    def test_get_changed_files_not_found(self) -> None:
        from tools.scripts.hooks.incremental_checks import get_changed_files

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_changed_files()
            assert result == []

    def test_get_staged_files_timeout(self) -> None:
        from tools.scripts.hooks.incremental_checks import get_staged_files

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            result = get_staged_files()
            assert result == []

    def test_get_staged_files_not_found(self) -> None:
        from tools.scripts.hooks.incremental_checks import get_staged_files

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_staged_files()
            assert result == []

    def test_run_diff_checks_no_files(self) -> None:
        from tools.scripts.hooks.incremental_checks import run_diff_checks

        with patch("tools.scripts.hooks.incremental_checks.get_changed_files", return_value=[]):
            passed, msg = run_diff_checks()
            assert passed is True
            assert "No changed" in msg

    def test_run_diff_checks_no_code_files(self, tmp_path: Path) -> None:
        from tools.scripts.hooks.incremental_checks import run_diff_checks

        fake_file = tmp_path / "readme.txt"
        fake_file.touch()
        with patch("tools.scripts.hooks.incremental_checks.get_changed_files", return_value=[fake_file]):
            passed, msg = run_diff_checks()
            assert passed is True
            assert "No code files" in msg

    def test_run_pre_commit_checks_no_files(self) -> None:
        from tools.scripts.hooks.incremental_checks import run_pre_commit_checks

        with patch("tools.scripts.hooks.incremental_checks.get_staged_files", return_value=[]):
            passed, msg = run_pre_commit_checks()
            assert passed is True
            assert "No staged" in msg

    def test_run_pre_commit_checks_no_code_files(self, tmp_path: Path) -> None:
        from tools.scripts.hooks.incremental_checks import run_pre_commit_checks

        fake_file = tmp_path / "readme.txt"
        fake_file.touch()
        with patch("tools.scripts.hooks.incremental_checks.get_staged_files", return_value=[fake_file]):
            passed, msg = run_pre_commit_checks()
            assert passed is True
            assert "No code files" in msg

    def test_check_code_files_all_pass(self, tmp_path: Path) -> None:
        from tools.scripts.hooks.incremental_checks import _check_code_files

        py_file = tmp_path / "good.py"
        py_file.write_text("x = 1\n")

        with (
            patch("tools.scripts.hooks.incremental_checks.run_lint_files", return_value=(True, "")),
            patch("tools.scripts.hooks.incremental_checks.run_format_files", return_value=(True, "")),
            patch("tools.scripts.hooks.incremental_checks.detect_language_from_file", return_value=None),
        ):
            passed, msg = _check_code_files([py_file], label="Test")
            assert passed is True
            assert "All" in msg

    def test_check_code_files_lint_fail(self, tmp_path: Path) -> None:
        from tools.scripts.hooks.incremental_checks import _check_code_files

        py_file = tmp_path / "bad.py"
        py_file.write_text("x = 1\n")

        with (
            patch("tools.scripts.hooks.incremental_checks.run_lint_files", return_value=(False, "lint error")),
            patch("tools.scripts.hooks.incremental_checks.run_format_files", return_value=(True, "")),
            patch("tools.scripts.hooks.incremental_checks.detect_language_from_file", return_value=None),
        ):
            passed, msg = _check_code_files([py_file], label="Test")
            assert passed is False
            assert "lint error" in msg

    def test_check_code_files_format_fail(self, tmp_path: Path) -> None:
        from tools.scripts.hooks.incremental_checks import _check_code_files

        py_file = tmp_path / "bad_fmt.py"
        py_file.write_text("x = 1\n")

        with (
            patch("tools.scripts.hooks.incremental_checks.run_lint_files", return_value=(True, "")),
            patch("tools.scripts.hooks.incremental_checks.run_format_files", return_value=(False, "format error")),
            patch("tools.scripts.hooks.incremental_checks.detect_language_from_file", return_value=None),
        ):
            passed, msg = _check_code_files([py_file], label="Test")
            assert passed is False
            assert "format error" in msg

    def test_check_code_files_violations(self, tmp_path: Path) -> None:
        from tools.scripts.hooks.incremental_checks import _check_code_files

        py_file = tmp_path / "violated.py"
        py_file.write_text("x = 1\n")

        mock_result = SimpleNamespace(
            file=str(py_file),
            language="python",
            passed=False,
            issues=[SimpleNamespace(severity="error", rule_id="r1", message="bad", line=1, column=1, category="c")],
        )

        with (
            patch("tools.scripts.hooks.incremental_checks.run_lint_files", return_value=(True, "")),
            patch("tools.scripts.hooks.incremental_checks.run_format_files", return_value=(True, "")),
            patch("tools.scripts.hooks.incremental_checks.detect_language_from_file", return_value="python"),
            patch("tools.scripts.hooks.incremental_checks.validate_file", return_value=mock_result),
        ):
            passed, msg = _check_code_files([py_file], label="Test")
            assert passed is False
            assert "violations" in msg


import subprocess  # noqa: E402

# ──────────────────────────────────────────────────────────
# report_generator.py
# ──────────────────────────────────────────────────────────


class TestReportGenerator:
    def _make_result(
        self, *, passed: bool = True, errors: int = 0, warnings: int = 0, infos: int = 0
    ) -> SimpleNamespace:
        issues = []
        for _ in range(errors):
            issues.append(
                SimpleNamespace(severity="error", rule_id="r1", message="err", line=1, column=1, category="c")
            )
        for _ in range(warnings):
            issues.append(
                SimpleNamespace(severity="warning", rule_id="r2", message="warn", line=2, column=1, category="c")
            )
        for _ in range(infos):
            issues.append(
                SimpleNamespace(severity="info", rule_id="r3", message="info", line=3, column=1, category="c")
            )
        return SimpleNamespace(
            file="test.py",
            language="python",
            passed=passed,
            error_count=errors,
            warning_count=warnings,
            info_count=infos,
            issues=issues,
            to_dict=lambda: {"file": "test.py", "language": "python"},
        )

    def test_junit_xml_passed(self) -> None:
        from tools.scripts.report_generator import generate_junit_xml

        xml = generate_junit_xml([self._make_result(passed=True)])
        assert "tests=" in xml
        assert 'failures="0"' in xml

    def test_junit_xml_failed_with_error(self) -> None:
        from tools.scripts.report_generator import generate_junit_xml

        xml = generate_junit_xml([self._make_result(passed=False, errors=1)])
        assert "failure" in xml.lower()

    def test_junit_xml_passed_with_warnings(self) -> None:
        from tools.scripts.report_generator import generate_junit_xml

        xml = generate_junit_xml([self._make_result(passed=True, warnings=2)])
        assert "system-out" in xml

    def test_junit_xml_passed_no_issues(self) -> None:
        from tools.scripts.report_generator import generate_junit_xml

        xml = generate_junit_xml([self._make_result(passed=True)])
        assert "testcase" in xml

    def test_html_report(self) -> None:
        from tools.scripts.report_generator import generate_html_report

        html = generate_html_report(
            [
                self._make_result(passed=True),
                self._make_result(passed=False, errors=1),
            ]
        )
        assert "<html" in html
        assert "FAIL" in html
        assert "PASS" in html

    def test_sarif(self) -> None:
        from tools.scripts.report_generator import generate_sarif

        sarif_str = generate_sarif([self._make_result(passed=False, errors=1)])
        sarif = json.loads(sarif_str)
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        assert len(sarif["runs"][0]["results"]) == 1

    def test_sarif_empty(self) -> None:
        from tools.scripts.report_generator import generate_sarif

        sarif_str = generate_sarif([])
        sarif = json.loads(sarif_str)
        assert sarif["runs"][0]["results"] == []

    def test_write_report_json(self) -> None:
        from tools.scripts.report_generator import write_report

        content = write_report([self._make_result()], "json")
        assert content is not None
        data = json.loads(content)
        assert "results" in data

    def test_write_report_junit(self) -> None:
        from tools.scripts.report_generator import write_report

        content = write_report([self._make_result()], "junit")
        assert content is not None
        assert "testsuite" in content

    def test_write_report_html(self) -> None:
        from tools.scripts.report_generator import write_report

        content = write_report([self._make_result()], "html")
        assert content is not None
        assert "<html" in content

    def test_write_report_sarif(self) -> None:
        from tools.scripts.report_generator import write_report

        content = write_report([self._make_result()], "sarif")
        assert content is not None
        assert "sarif" in content.lower()

    def test_write_report_unknown_format(self) -> None:
        from tools.scripts.report_generator import write_report

        result = write_report([], "unknown")
        assert result is None

    def test_write_report_to_file(self, tmp_path: Path) -> None:
        from tools.scripts.report_generator import write_report

        out = tmp_path / "report.json"
        content = write_report([self._make_result()], "json", output=out)
        assert out.exists()
        assert content is not None

    def test_xml_escape(self) -> None:
        from tools.scripts.report_generator import _xml_escape

        assert _xml_escape('<a>&"') == "&lt;a&gt;&amp;&quot;"

    def test_html_escape(self) -> None:
        from tools.scripts.report_generator import _html_escape

        assert _html_escape("<a>&") == "&lt;a&gt;&amp;"


# ──────────────────────────────────────────────────────────
# contributor_dashboard.py
# ──────────────────────────────────────────────────────────


class TestContributorDashboard:
    def test_analyze_case_studies_no_dir(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        d = ContributorDashboard(tmp_path)
        stats = d.analyze_case_studies()
        assert stats["total"] == 0

    def test_analyze_case_studies_with_cases(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        cases_dir = tmp_path / "case-studies"
        cases_dir.mkdir()
        (cases_dir / "case1.md").write_text("项目类型: CLI工具\nAI 工具栈: Claude\n效率提升: 5x")
        (cases_dir / "case2.md").write_text("项目类型: Web应用\nAI 工具栈: GPT-4\n效率提升: 3x")
        (cases_dir / "README.md").write_text("skip me")

        d = ContributorDashboard(tmp_path)
        stats = d.analyze_case_studies()
        assert stats["total"] == 2
        assert stats["avg_boost"] == 4.0

    def test_analyze_tool_matrix_no_file(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        d = ContributorDashboard(tmp_path)
        stats = d.analyze_tool_matrix()
        assert stats["total"] == 0

    def test_analyze_tool_matrix(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        matrix_dir = tmp_path / "docs" / "tools"
        matrix_dir.mkdir(parents=True)
        (matrix_dir / "ai-tool-matrix.md").write_text(
            "✅ **推荐** tool1\n⚠️ **稳定** tool2\n❌ **遗留** tool3\n✅ **推荐** tool4"
        )

        d = ContributorDashboard(tmp_path)
        stats = d.analyze_tool_matrix()
        assert stats["recommended"] == 2
        assert stats["stable"] == 1
        assert stats["legacy"] == 1
        assert stats["total"] == 4

    def test_analyze_docs_coverage_no_dir(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        d = ContributorDashboard(tmp_path)
        stats = d.analyze_docs_coverage()
        assert stats["total"] == 0

    def test_analyze_docs_coverage(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        docs = tmp_path / "docs"
        (docs / "efficiency").mkdir(parents=True)
        (docs / "tools").mkdir(parents=True)
        (docs / "efficiency" / "a.md").write_text("a")
        (docs / "efficiency" / "b.md").write_text("b")
        (docs / "tools" / "c.md").write_text("c")

        d = ContributorDashboard(tmp_path)
        stats = d.analyze_docs_coverage()
        assert stats["total"] == 3
        assert stats["categories"]["efficiency"] == 2

    def test_generate_dashboard_markdown(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        # Create minimal docs structure
        (tmp_path / "docs").mkdir()
        d = ContributorDashboard(tmp_path)
        result = d.generate_dashboard("markdown")
        assert "仪表板" in result

    def test_generate_dashboard_json(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        d = ContributorDashboard(tmp_path)
        result = d.generate_dashboard("json")
        data = json.loads(result)
        assert "case_studies" in data

    def test_generate_dashboard_unknown(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        d = ContributorDashboard(tmp_path)
        result = d.generate_dashboard("unknown")
        assert result == ""

    def test_main(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import main

        out = tmp_path / "dash.md"
        with patch("sys.argv", ["prog", "--format", "markdown", "--output", str(out)]):
            main()
        assert out.exists()

    def test_main_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.contributor_dashboard import main

        with patch("sys.argv", ["prog", "--format", "json"]):
            main()
        captured = capsys.readouterr()
        assert "case_studies" in captured.out

    def test_analyze_contributors_error(self, tmp_path: Path) -> None:
        from tools.scripts.contributor_dashboard import ContributorDashboard

        d = ContributorDashboard(tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            stats = d.analyze_contributors()
            assert stats["total_contributors"] == 0
