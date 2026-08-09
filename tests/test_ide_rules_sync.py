from __future__ import annotations

from pathlib import Path

from tools.scripts.ide_rules_sync import generate_ide_rules


def test_generate_ide_rules(tmp_path: Path) -> None:
    paths = generate_ide_rules(tmp_path)

    assert "cursorrules" in paths
    assert "windsurfrules" in paths

    cursorrules_file = paths["cursorrules"]
    windsurfrules_file = paths["windsurfrules"]

    assert cursorrules_file.exists()
    assert windsurfrules_file.exists()

    cursorrules_content = cursorrules_file.read_text(encoding="utf-8")
    windsurfrules_content = windsurfrules_file.read_text(encoding="utf-8")

    assert "Governance Standards" in cursorrules_content
    assert "Quality Gates" in cursorrules_content
    assert "Windsurf Rules" in windsurfrules_content
    assert "Zero Tolerance for Type Suppression" in windsurfrules_content
