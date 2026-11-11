"""P-01: `adg check` 默认并行度解析契约。

历史行为：`cmd_check` 用 `int(getattr(args, "jobs", None) or 1)`，导致
未显式传 `--jobs` 时永远串行，`[tool.adg].jobs`（默认 4）形同虚设，
与 `check_directory` / hooks 路径的默认并行度不一致。

契约：
1. 显式 `--jobs N`（N > 0）优先；
2. 未指定（或 <=0）时取 `[tool.adg].jobs`（经 `app_config.get_setting`）；
3. 配置非法（非数字 / <=0）回退 4，不阻断检查；
4. JSON 输出 `meta.jobs` 必须与**实际执行**使用的并行度一致。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from tools.scripts.adg_cli.commands.cmd import cmd_check as cc


def _ns(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "path": ".",
        "lang": "python",
        "framework": None,
        "severity": None,
        "json": False,
        "sarif": False,
        "jobs": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestResolveJobs:
    def test_explicit_jobs_wins_over_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 8)
        assert cc._resolve_jobs(_ns(jobs=2)) == 2

    def test_uses_configured_default_when_not_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 3)
        assert cc._resolve_jobs(_ns(jobs=None)) == 3

    def test_missing_jobs_attribute_uses_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """老测试/调用方可能构造不含 jobs 的 Namespace，不得 AttributeError。"""
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 2)
        args = argparse.Namespace(path=".")
        assert cc._resolve_jobs(args) == 2

    @pytest.mark.parametrize("configured", ["abc", "", None, 0, -1, 2.5])
    def test_invalid_config_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch, configured: object) -> None:
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: configured)
        assert cc._resolve_jobs(_ns(jobs=None)) == cc._DEFAULT_JOBS

    def test_non_positive_explicit_jobs_falls_back_to_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 6)
        assert cc._resolve_jobs(_ns(jobs=0)) == 6
        assert cc._resolve_jobs(_ns(jobs=-2)) == 6

    def test_invalid_explicit_jobs_falls_back_to_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 5)
        assert cc._resolve_jobs(_ns(jobs="not-a-number")) == 5

    def test_repo_config_default_is_parallel(self) -> None:
        """仓库自身 [tool.adg].jobs = 4：日常 `adg check .` 必须是并行的。"""
        assert cc._resolve_jobs(_ns(jobs=None)) == cc._DEFAULT_JOBS


class TestJsonMetaJobs:
    def test_meta_jobs_matches_execution(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")

        executed: dict[str, int] = {}

        def fake_run_checks(files: list[Path], rules: dict, severity: str | None, jobs: int) -> list:
            executed["jobs"] = jobs
            return []

        monkeypatch.setattr(cc, "_run_checks", fake_run_checks)
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 3)

        result = cc.cmd_check(_ns(path=str(tmp_path), json=True))

        assert result == 0
        assert executed["jobs"] == 3, "配置值未传入实际执行路径"
        data = json.loads(capsys.readouterr().out)
        assert data["meta"]["jobs"] == 3, "JSON meta 未反映实际并行度"
        assert data["meta"]["cache_supported"] is False
        assert data["meta"]["cache_reason"] == "adg_cli_path_no_rules_engine_cache"

    def test_explicit_jobs_reflected_in_meta(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

        monkeypatch.setattr(cc, "_run_checks", lambda *a, **k: [])
        monkeypatch.setattr(cc, "get_setting", lambda key, default=None: 8)

        result = cc.cmd_check(_ns(path=str(tmp_path), json=True, jobs=2))

        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["meta"]["jobs"] == 2
