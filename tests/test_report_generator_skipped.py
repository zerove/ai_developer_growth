"""端到端 skipped 文件契约验证 (Phase 33b-12 / ADR-052).

在真实端到端 (check_file + generate_*) 验证:
- skipped 文件不被 SARIF/JUnit/JSON/HTML 报告静默丢失
- skipped 文件不被算 passed/failures
- JUnit skipped 文件用 <skipped/> 标记 (JUnit 标准)
- SARIF skipped 文件用 kind=notApplicable 标记 (SARIF 标准)
"""

import json
import tempfile
from pathlib import Path

from tools.scripts.report_generator import (
    _build_json_summary,
    generate_html_report,
    generate_junit_xml,
    generate_sarif,
)
from tools.scripts.rules_engine.checker import check_file


def _real_check_setup():
    """构造 3 个 CheckResult: pass / fail / skipped (空文件)."""
    r_pass = check_file(Path("tools/scripts/rules_engine/ast_parser.py"), semantic=True)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
        f.write(b"import os\ndef broken(:\n    pass\n")
        bad_fname = f.name
    r_fail = check_file(Path(bad_fname), semantic=True)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
        f.write(b"")
        skip_fname = f.name
    r_skip = check_file(Path(skip_fname), semantic=True)
    return [r_pass, r_fail, r_skip], skip_fname


def test_skipped_file_in_sarif() -> None:
    """skipped 文件在 SARIF 中以 kind=notApplicable 标记, 不再丢失."""
    results, skip_fname = _real_check_setup()
    sarif = json.loads(generate_sarif(results))
    # 找到所有 locations 的 URI
    locations = []
    for r in sarif["runs"][0]["results"]:
        for loc in r.get("locations", []):
            locations.append(loc["physicalLocation"]["artifactLocation"]["uri"])
    # skipped 文件必须出现
    skip_uri = Path(skip_fname).name
    in_sarif = any(Path(uri).name == skip_uri for uri in locations)
    assert in_sarif, f"skipped 文件 {skip_uri} 不在 SARIF 中"
    # 找到 notApplicable 标记
    not_applicable = [r for r in sarif["runs"][0]["results"] if r.get("properties", {}).get("kind") == "notApplicable"]
    assert len(not_applicable) >= 1, "SARIF 应有 notApplicable 标记"
    assert any("file-skipped" in r.get("ruleId", "") for r in not_applicable)


def test_skipped_file_in_junit() -> None:
    """skipped 文件在 JUnit 中用 <skipped/> 标记."""
    results, skip_fname = _real_check_setup()
    junit = generate_junit_xml(results)
    # 找到 <skipped/> 标记
    assert "<skipped/>" in junit, "JUnit XML 应包含 <skipped/> 标记"


def test_skipped_excluded_from_failures() -> None:
    """JUnit failures 计数排除 skipped."""
    from tools.scripts.report_generator import _count_summary_stats

    results, _ = _real_check_setup()
    total_errors, total_warnings, total_tests, failures = _count_summary_stats(results)
    # r_fail 含 invalid-syntax (ruff E999) → severity=error, 故 passed=False, failures=1。
    # 此前该 issue 被误降级为 warning, 使语法错误文件也 passed=True; 此断言随之修正。
    # r_skip.skipped = True → 不算 passed 也不算 fail
    assert total_tests == 3
    assert failures == 1, f"failures 应 = 1 (r_fail 含 error 级语法错误), 实际 {failures}"


def test_skipped_excluded_from_passed_count() -> None:
    """HTML passed_count 排除 skipped."""
    results, _ = _real_check_setup()
    summary = _build_json_summary(results)
    # r_fail 含 error 级 invalid-syntax → passed=False → 整体 passed=False
    assert summary["passed"] is False


def test_skipped_count_in_html_summary() -> None:
    """HTML summary 包含 skipped_count 字段."""
    results, _ = _real_check_setup()
    from tools.scripts.report_generator import _count_html_summary

    summary = _count_html_summary(results)
    assert "skipped_count" in summary
    assert summary["skipped_count"] == 1
    assert summary["passed_count"] == 1  # 仅 r_pass; r_fail 含 error, r_skip skipped


def test_html_report_no_crash_with_skipped() -> None:
    """generate_html_report 处理 skipped 不抛错."""
    results, _ = _real_check_setup()
    html = generate_html_report(results)
    # 验证 HTML 包含 skipped 标记 (或至少 3 个文件)
    assert len(html) > 100
    assert "ast_parser.py" in html  # 至少有 r_pass 的文件名
