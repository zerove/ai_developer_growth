"""hallucination_detector 第二轮: 字符串/注释豁免/文件目录扫描/报告格式化。66%→90%+"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.hallucination_detector import (
    HallucinationFinding,
    HallucinationReport,
    _is_comment,
    _is_in_string,
    _scan_line_for_patterns,
    detect_hallucinations,
    detect_hallucinations_in_file,
    format_hallucination_report,
)


class TestStringAndCommentExemption:
    def test_in_string_detection(self) -> None:
        assert _is_in_string('x = "os.listdir(recursive=True)"', 5) is True
        assert _is_in_string("x = os.listdir(recursive=True)", 5) is False

    def test_comment_detection_hash(self) -> None:
        assert _is_comment("# os.listdir(recursive=True)", 5) is True
        assert _is_comment("x = 1  # trailing", 5) is False

    def test_comment_detection_slash_slash(self) -> None:
        assert _is_comment("// os.listdir(recursive=True)", 10) is True

    def test_in_string_escape_handling(self) -> None:
        # 转义引号不结束字符串: pos 落在后半段仍在字符串内
        line = r'x = "a\" + os.listdir(recursive=True)"'
        assert _is_in_string(line, 20) is True

    def test_comment_skips_quoted_slashes(self) -> None:
        # 引号内的 // 不算注释起点
        assert _is_comment('url = "http://x"  # real', 22) is True
        # pos 在 // 之后才判真; 在其之前判假
        assert _is_comment("a // b", 5) is True
        assert _is_comment("a // b", 0) is False

    def test_scan_skips_string_content(self) -> None:
        report = HallucinationReport(files_scanned=0, findings=[])
        _scan_line_for_patterns('doc = "use os.listdir(path, recursive=True)"', 1, Path("a.py"), report)
        assert report.findings == []

    def test_scan_catches_real_usage(self) -> None:
        report = HallucinationReport(files_scanned=0, findings=[])
        _scan_line_for_patterns("items = os.listdir(base, recursive=True)", 3, Path("a.py"), report)
        assert len(report.findings) == 1
        assert report.findings[0].line == 3


class TestFileScan:
    def test_ignored_files_shortcircuit(self, tmp_path: Path) -> None:
        # _IGNORE_FILES 内置引擎自身文件名（含模式文本自身，扫描会自报）
        lock = tmp_path / "auto_fix.py"
        lock.write_text("os.listdir(recursive=True)\n", encoding="utf-8")
        report = detect_hallucinations_in_file(lock)
        assert report.files_scanned == 1 and report.total_findings == 0

    def test_non_ignored_same_content_hits(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("os.listdir(p, recursive=True)\n", encoding="utf-8")
        report = detect_hallucinations_in_file(f)
        assert report.total_findings == 1

    def test_ignored_dir_shortcircuit(self, tmp_path: Path) -> None:
        d = tmp_path / "anti_patterns"
        d.mkdir()
        f = d / "dirty.py"
        f.write_text("os.listdir(p, recursive=True)\n", encoding="utf-8")
        report = detect_hallucinations_in_file(f)
        assert report.files_scanned == 1 and report.total_findings == 0

    def test_unreadable_file_returns_zero(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.py"
        bad.write_bytes(b"\xff\xfe\x00\x01")
        report = detect_hallucinations_in_file(bad)
        assert report.files_scanned == 0

    def test_clean_and_dirty_mixed(self, tmp_path: Path) -> None:
        f = tmp_path / "mixed.py"
        f.write_text(
            "# hallucinated-api comment 不算\n"
            "result = json.load(f, indent=2)\n"  # 命中
            's = "requests.post(url, timeout=True)"\n'  # 字符串豁免
            "ok = compute(x)\n",
            encoding="utf-8",
        )
        report = detect_hallucinations_in_file(f)
        assert report.files_scanned == 1
        assert all(f2.line != 4 for f2 in report.findings)


class TestDirectoryScan:
    def test_multi_file_aggregation(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("json.load(f, indent=2)\n", encoding="utf-8")
        sub = tmp_path / "node_modules"
        sub.mkdir()
        (sub / "dirty.js").write_text("os.listdir(p, recursive=true)\n", encoding="utf-8")
        report = detect_hallucinations(tmp_path)
        assert report.files_scanned >= 1
        assert report.total_findings == len(report.findings)
        assert report.high_count + report.medium_count + report.low_count <= report.total_findings


class TestFormatReport:
    def test_empty_report_message(self) -> None:
        text = format_hallucination_report(HallucinationReport(files_scanned=3))
        assert "✅ No hallucination patterns detected." in text
        assert "Files scanned: 3" in text

    def test_grouped_by_severity_with_icons(self) -> None:
        finding_high = HallucinationFinding(
            file="a.py",
            line=1,
            column=0,
            pattern_id="p-high",
            severity="high",
            category="c",
            message="m1",
            evidence="evidence-line",
            confidence=0.9,
        )
        finding_low = HallucinationFinding(
            file="b.go",
            line=7,
            column=2,
            pattern_id="p-low",
            severity="low",
            category="c",
            message="m2",
            evidence="ev2",
            confidence=0.5,
        )
        report = HallucinationReport(files_scanned=2, findings=[finding_high, finding_low])
        report._recount()
        text = format_hallucination_report(report)
        assert "🔴 HIGH SEVERITY (1 findings)" in text
        assert "🔵 LOW SEVERITY (1 findings)" in text
        assert "a.py:1 [p-high]" in text and "Confidence: 90%" in text
