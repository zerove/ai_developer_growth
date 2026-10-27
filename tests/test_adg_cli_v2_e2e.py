# 拆分自 tests/test_adg_cli_v2.py

"""Phase 27: Comprehensive tests for adg_cli.py (43% -> 80%)."""

from __future__ import annotations

import types


def test_check_sarif_output_e2e(tmp_path, monkeypatch, capsys):
    """check --sarif 应输出合法 SARIF 2.1.0（GitHub Code Scanning 集成契约）。"""
    import json as _json

    target = tmp_path / "bad.py"
    target.write_text("x = eval('1+1')\n", encoding="utf-8")

    from tools.scripts.adg_cli.commands import cmd_check

    args = types.SimpleNamespace(
        path=str(target),
        lang="python",
        severity="info",
        json=False,
        sarif=True,
        framework=None,
        with_docs=False,
        no_trend=True,
        notify=None,
        min_severity=None,
        exclude=None,
    )
    rc = cmd_check(args)
    out = capsys.readouterr().out
    data = _json.loads(out)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["tool"]["driver"]["name"] == "adg"
    assert len(data["runs"][0]["results"]) > 0
    assert rc != 0  # 有 error 级问题时非零退出


def test_fix_smart_e2e(tmp_path, capsys):
    """fix --smart 应经 AutoFixOrchestrator 用 Ruff 修复未用导入。"""
    import json as _json

    target = tmp_path / "messy.py"
    target.write_text("import os\nimport sys\nx = 1\n", encoding="utf-8")

    from tools.scripts.adg_cli.commands import cmd_fix

    args = types.SimpleNamespace(
        path=str(target),
        lang="python",
        json=True,
        smart=True,
    )
    rc = cmd_fix(args)
    out = capsys.readouterr().out
    stats = _json.loads(out)
    assert stats["mode"] == "smart"
    assert stats["errors"] == 0
    assert stats["fixes_applied"] > 0
    assert "import os" not in target.read_text(encoding="utf-8")
    assert rc == 0


def test_fix_regex_mode_unchanged(tmp_path):
    """默认（正则）模式行为保持: py-bare-except 可被修复。"""
    target = tmp_path / "legacy.py"
    target.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    from tools.scripts.adg_cli.fix import fix_file

    result = fix_file(target)
    assert result["errors"] == 0
    assert result["fixed"] >= 1
    assert "except Exception:" in target.read_text(encoding="utf-8")
