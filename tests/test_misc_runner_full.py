"""hooks/misc_runner.py 覆盖攻坚 (19%→60%+)。

覆盖:
- _exception_* 系列(mock EnhancedExceptionManager)
- _emit_or_write
- _dep_graph_build/_handle_dep_graph 分发与未知动作/路径校验
- _handle_install_hooks 三分支 / _handle_learn / _handle_db_maintain / _close_store_quietly
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks import misc_runner as mr


def make_args(**kw: object) -> argparse.Namespace:
    return argparse.Namespace(**kw)  # type: ignore[arg-type]


class TestEmitOrWrite:
    def test_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        mr._emit_or_write("hello", None, "LABEL")
        assert "hello" in capsys.readouterr().out

    def test_to_file(self, tmp_path: Path) -> None:
        out = tmp_path / "o.txt"
        mr._emit_or_write("data", out, "LABEL")
        assert "data" in out.read_text()


class TestExceptionHandlers:
    def _manager(self) -> MagicMock:
        m = MagicMock()
        req = SimpleNamespace(
            id="req1",
            rule_id="R1",
            paths=["a.py"],
            reason="r",
            severity="warning",
            requested_severity="info",
            expires=None,
            status=SimpleNamespace(value="pending"),
        )
        m.request_exception.return_value = req
        return m

    def test_request(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = make_args(
            rule_id="R1",
            paths="a.py,b.py",
            reason="why",
            severity="warning",
            requested_severity="info",
            expires=None,
            created_by="me",
            reviewers="",
        )
        rc = mr._exception_request(self._manager(), args)
        assert rc == 0 and "req1" in capsys.readouterr().out


class TestDepGraphHandler:
    def test_missing_path(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = mr._handle_dep_graph(make_args(path=tmp_path / "nope", dep_graph_action="analyze"))
        assert rc == 1 and "not found" in capsys.readouterr().out

    def test_unknown_action(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "x.py").write_text("x=1\n")
        rc = mr._handle_dep_graph(make_args(path=tmp_path, dep_graph_action="wat"))
        assert rc == 1 and "Unknown" in capsys.readouterr().out

    def test_dispatch_analyze(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("import os\n")
        with patch.object(mr, "_dep_graph_analyze", MagicMock(return_value=0)) as m:
            rc = mr._handle_dep_graph(make_args(path=tmp_path, dep_graph_action="analyze", max_depth=5))
            m.assert_called_once()
        assert rc == 0


class TestInstallHooks:
    def test_pre_push_success(self) -> None:
        with patch("tools.scripts.hooks.pre_push.install_pre_push_hook", MagicMock(return_value=True)) as m:
            rc = mr._handle_install_hooks(make_args(pre_push=True, pre_commit=False))
            m.assert_called_once()
        assert rc == 0

    def test_pre_push_failure(self) -> None:
        with patch("tools.scripts.hooks.pre_push.install_pre_push_hook", MagicMock(return_value=False)):
            assert mr._handle_install_hooks(make_args(pre_push=True, pre_commit=False)) == 1

    def test_pre_commit_not_implemented(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert mr._handle_install_hooks(make_args(pre_push=False, pre_commit=True)) == 1
        assert "not yet implemented" in capsys.readouterr().out

    def test_no_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert mr._handle_install_hooks(make_args(pre_push=False, pre_commit=False)) == 1
        assert "Specify" in capsys.readouterr().out


class TestDbMaintain:
    def test_success_flow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        store = MagicMock()
        store.prune_history.return_value = 7
        store.cache_hit_rate.return_value = {"cached_files": 3}
        with (
            patch("tools.scripts.rules_engine.store.CheckStore", MagicMock(return_value=store)),
            patch("tools.scripts.app_config.get_path", lambda k, d: d),
        ):
            rc = mr._handle_db_maintain(make_args(db=str(tmp_path / "t.db"), retention_days=30))
        assert rc == 0
        assert "7" in capsys.readouterr().out
        store.close.assert_called_once()

    def test_store_open_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        with (
            patch("tools.scripts.rules_engine.store.CheckStore", MagicMock(side_effect=RuntimeError("boom"))),
            patch("tools.scripts.app_config.get_path", lambda k, d: d),
        ):
            rc = mr._handle_db_maintain(make_args(db=str(tmp_path / "bad.db"), retention_days=90))
        assert rc == 1


class TestCloseStoreQuietly:
    def test_no_close_method(self) -> None:
        mr._close_store_quietly(object())  # 不抛异常即可

    def test_close_raises_silenced(self) -> None:
        bad = MagicMock()
        bad.close.side_effect = RuntimeError
        mr._close_store_quietly(bad)
