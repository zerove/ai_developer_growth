"""hallucination_detector 扫描主路径测试（改进建议 8 补强）。

覆盖 detect_hallucinations_in_file 对真实文件内容的判定行为。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.hallucination_detector import (
    detect_hallucinations_in_file,
    format_hallucination_report,
)


class TestDetectInFile:
    def test_python_file_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(
            '"""Mod."""\n'
            "import requests\n"
            "\n"
            "def call():\n"
            '    """Doc."""\n'
            "    return requests.post('http://x', json={})\n",
            encoding="utf-8",
        )
        report = detect_hallucinations_in_file(f)
        # 只验证扫描管线可用: 返回报告且 files_scanned 计入
        assert report is not None
        assert report.files_scanned >= 1

    def test_ignored_file_skipped(self, tmp_path: Path) -> None:
        d = tmp_path / "__pycache__"
        d.mkdir()
        f = d / "ignored.py"
        f.write_text("x = 1\n", encoding="utf-8")
        report = detect_hallucinations_in_file(f)
        assert report.findings == []

    def test_format_report_renders(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n", encoding="utf-8")
        report = detect_hallucinations_in_file(f)
        text = format_hallucination_report(report)
        assert isinstance(text, str) and len(text) > 0
