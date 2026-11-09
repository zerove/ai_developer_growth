"""Tests for the capability-radar CLI entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cli


def test_demo_mode_prints_and_exports(tmp_path, monkeypatch, capsys):
    markdown = tmp_path / "report.md"
    json_out = tmp_path / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["capability-radar", "--demo", "-o", str(markdown), "--json", str(json_out)],
    )

    assert cli.main() == 0

    out = capsys.readouterr().out
    assert "演示模式" in out
    assert markdown.exists() and markdown.stat().st_size > 0
    assert json_out.exists() and json_out.stat().st_size > 0


def test_input_mode_reads_json(tmp_path, monkeypatch):
    sample = Path(__file__).parent / "sample_answers_l2.json"
    assert sample.exists(), "示例答案文件缺失，用例失去意义"
    monkeypatch.setattr(
        sys,
        "argv",
        ["capability-radar", "-i", str(sample)],
    )

    assert cli.main() == 0

    assert not (tmp_path / "report.md").exists()
