"""check_directory skipped 文件端到端契约验证 (Phase 33b-13 / ADR-053).

验证 _check_files_serial 不再静默过滤 skipped 文件.
修复前: 空文件 (0 字节) 在 check_directory 结果中**完全丢失**.
修复后: skipped 文件以 CheckResult.skipped=True 形式返回, 报告层可正确显示.
"""

import json
import tempfile
from pathlib import Path

from tools.scripts.report_generator import generate_junit_xml, generate_sarif
from tools.scripts.rules_engine.checker import check_directory


def test_check_directory_includes_skipped_files() -> None:
    """check_directory 返回 skipped 文件 (不静默丢失)."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "empty.py").write_text("")
        (p / "real.py").write_text("x = 1\n")
        results = check_directory(p, languages=["python"])
        # 修复前: 1 个结果 (real.py), empty.py 静默丢失
        # 修复后: 2 个结果, empty.py skipped=True
        assert len(results) == 2, f"应返回 2 个结果, 实际 {len(results)}"
        file_names = {Path(r.file).name for r in results}
        assert file_names == {"empty.py", "real.py"}
        # empty.py 应 skipped=True
        empty_result = [r for r in results if Path(r.file).name == "empty.py"][0]
        assert empty_result.skipped is True
        assert empty_result.issues == []
        # real.py 应 passed=True, skipped=False
        real_result = [r for r in results if Path(r.file).name == "real.py"][0]
        assert real_result.skipped is False
        assert real_result.passed is True


def test_check_directory_skipped_in_sarif_end_to_end() -> None:
    """end-to-end: check_directory → generate_sarif, skipped 文件在 SARIF 中."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "empty.py").write_text("")
        results = check_directory(p, languages=["python"])
        sarif = json.loads(generate_sarif(results))
        # 找到 notApplicable 标记
        not_applicable = [
            r
            for r in sarif["runs"][0]["results"]
            if r.get("properties", {}).get("kind") == "notApplicable"
        ]
        assert len(not_applicable) == 1, (
            f"应有 1 个 notApplicable 标记, 实际 {len(not_applicable)}"
        )
        assert "empty.py" in not_applicable[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]


def test_check_directory_skipped_in_junit_end_to_end() -> None:
    """end-to-end: check_directory → generate_junit, skipped 文件用 <skipped/>."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "empty.py").write_text("")
        results = check_directory(p, languages=["python"])
        junit = generate_junit_xml(results)
        assert "<skipped/>" in junit, "JUnit XML 应包含 <skipped/> 标记"
