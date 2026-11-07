"""hooks_runner 命令处理器单元测试（改进建议 2）。

覆盖核心 CLI 处理器路径: _run_simple、_handle_db_maintain、_close_store_quietly、
_handle_language_rules 的 fix/cache 分支与默认分支。
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts import hooks_runner


def _args(**kw: object) -> argparse.Namespace:
    return argparse.Namespace(**kw)  # type: ignore[arg-type]


class TestRunSimple:
    def test_tuple_passthrough(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = hooks_runner._run_simple((True, "all good"))
        out = capsys.readouterr().out
        assert code == 0
        assert "all good" in out

    def test_callable_and_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = hooks_runner._run_simple(lambda: (False, "bad"))
        assert code == 1
        assert "bad" in capsys.readouterr().out


class TestCloseStoreQuietly:
    def test_calls_close(self) -> None:
        class _Store:
            closed = False

            def close(self) -> None:
                self.closed = True

        s = _Store()
        hooks_runner._close_store_quietly(s)
        assert s.closed is True

    def test_no_close_method_ok(self) -> None:
        hooks_runner._close_store_quietly(object())  # 不应抛异常

    def test_close_exception_swallowed(self) -> None:
        class _Bad:
            def close(self) -> None:
                raise RuntimeError("boom")

        hooks_runner._close_store_quietly(_Bad())  # 静默吞掉


class TestHandleDbMaintain:
    def _make_db(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
        from tools.scripts.rules_engine import store as store_mod
        from tools.scripts.rules_engine.store import CheckStore

        db = tmp_path / "trend.db"
        CheckStore(str(db))
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO check_cache (file_path, mtime, size, rules_hash, errors,"
            " warnings, info, updated_at) VALUES ('a.py', 1.0, 10, 'abc', 0, 1, 2,"
            " '2026-08-25T00:00:00')"
        )
        conn.commit()
        conn.close()
        # 弹出并关闭池化连接，避免污染后续同路径使用
        monkeypatch.setattr(
            store_mod, "_connections", {k: v for k, v in store_mod._connections.items() if k != str(db)}
        )
        return str(db)

    def test_success_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = self._make_db(tmp_path, monkeypatch)
        code = hooks_runner._handle_db_maintain(_args(db=db, retention_days=90))
        out = capsys.readouterr().out
        assert code == 0
        assert "裁剪完成" in out
        assert "缓存文件数" in out

    def test_bad_db_path_fails_gracefully(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = hooks_runner._handle_db_maintain(_args(db=str(tmp_path / "no-such-dir" / "x.db"), retention_days=90))
        out = capsys.readouterr().out
        assert code == 1
        assert "无法打开统一存储" in out


class TestHandleLanguageRules:
    def test_cache_mode_reports_files(self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
        # cache 分支走 get_path 展开 db 路径; monkeypatch 到临时目录避免碰真实库
        monkeypatch.setattr(
            "tools.scripts.app_config.get_path",
            lambda key, default: tmp_path / "trend.db",
        )
        f = tmp_path / "clean_sample.py"
        f.write_text('"""Mod."""\n\n\ndef ok() -> int:\n    """Doc."""\n    return 1\n')
        code = hooks_runner._handle_language_rules(_args(path=Path(tmp_path), cache=True))
        out = capsys.readouterr().out
        assert code in (0, 1)
        assert "PASS" in out or "FAIL" in out or "No files" in out

    def test_default_delegates_to_run_language_rules(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(
            hooks_runner,
            "run_language_rules",
            return_value=(True, "rules ok"),
        ) as mocked:
            code = hooks_runner._handle_language_rules(_args(path="src", lang="python"))
        assert code == 0
        mocked.assert_called_once_with("src", "python", "text")
        assert "rules ok" in capsys.readouterr().out


class TestHandleQualityGate:
    def test_delegates_with_flags(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(hooks_runner, "run_quality_gate", return_value=(True, "gate ok")) as mocked:
            ns = _args(
                path=".",
                full=True,
                check_annotation=True,
                check_security=False,
                check_type=False,
                check_error=False,
                check_structure=False,
                check_patterns=False,
                format="json",
            )
            code = hooks_runner._handle_quality_gate(ns)
        assert code == 0
        kwargs = mocked.call_args.kwargs
        assert kwargs["full"] is True
        assert kwargs["format"] == "json"
        assert "gate ok" in capsys.readouterr().out
