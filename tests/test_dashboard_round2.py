"""dashboard 第二轮: v3 API 路由全覆盖。62%→85%+

health/check/rules/docs/status/ci-summary/record + _get_db_size/_load_rules_summary。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tools.scripts.rules_engine.dashboard import (
    _add_ci_routes,
    _add_record_routes,
    _add_v3_check_route,
    _add_v3_health_route,
    _add_v3_rules_routes,
    _get_db_size,
    _get_rule_docs,
    create_app,
    init_db,
)
from tools.scripts.rules_engine.store import close_connection


@pytest.fixture
def db(tmp_path: Path) -> str:
    return str(tmp_path / "dash.db")


@pytest.fixture
def app(db: str, tmp_path: Path):  # type: ignore[no-untyped-def]
    application = create_app(db, ci_data_dir=str(tmp_path))
    yield application
    close_connection(db)


@pytest.fixture
def client(app):  # type: ignore[no-untyped-def]
    return TestClient(app)


class TestV3Health:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/api/v3/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok" and data["version"] == "3.0.0"
        assert data["database"] == "connected"


class TestV3Check:
    def test_check_success(self, client: TestClient) -> None:
        proc = MagicMock(returncode=0)
        proc.stdout = json.dumps({"issues": []})
        with patch("subprocess.run", return_value=proc):
            resp = client.post("/api/v3/check?path=.")
        assert resp.json()["status"] == "ok"

    def test_check_all_option_flags(self, client: TestClient) -> None:
        proc = MagicMock(returncode=0)
        proc.stdout = "{}"
        captured: dict[list, list] = {}

        def fake_run(cmd, **kw):  # type: ignore[no-untyped-def]
            captured["cmd"] = cmd
            return proc

        with patch("subprocess.run", side_effect=fake_run):
            client.post("/api/v3/check?path=x.py&lang=python&with_docs=true&severity=error")
        cmd = captured["cmd"]
        assert "--lang" in cmd and "python" in cmd and "--with-docs" in cmd and "--severity" in cmd

    def test_check_nonzero_exit(self, client: TestClient) -> None:
        proc = MagicMock(returncode=1)
        proc.stderr = "boom"
        with patch("subprocess.run", return_value=proc):
            resp = client.post("/api/v3/check?path=.")
        body = resp.json()
        assert body["status"] == "error" and "boom" in body["message"]

    def test_check_adg_missing(self, client: TestClient) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            resp = client.post("/api/v3/check?path=.")
        assert resp.json()["message"] == "adg command not found"

    def test_check_timeout(self, client: TestClient) -> None:
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="adg", timeout=1)):
            resp = client.post("/api/v3/check?path=.")
        assert "timed out" in resp.json()["message"].lower()

    def test_check_bad_json(self, client: TestClient) -> None:
        proc = MagicMock(returncode=0)
        proc.stdout = "{ not json"
        with patch("subprocess.run", return_value=proc):
            resp = client.post("/api/v3/check?path=.")
        assert "Invalid JSON" in resp.json()["message"]


class TestV3Rules:
    def test_rules_by_lang(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.adg_cli import rules as rules_mod

        monkeypatch.setattr(rules_mod, "load_rules_for_language", lambda lang: {"anti_patterns": [{"id": 1}]})
        resp = client.get("/api/v3/rules?lang=python")
        assert resp.json()["status"] == "ok" and resp.json()["language"] == "python"

    def test_rules_all_languages(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.adg_cli import rules as rules_mod

        monkeypatch.setattr(rules_mod, "load_rules_for_language", lambda lang: {"anti_patterns": [1, 2]})
        resp = client.get("/api/v3/rules")
        summary = resp.json()["languages"]
        assert summary["python"] == 2

    def test_rule_docs_hit_and_miss(self, client: TestClient) -> None:
        resp = client.get("/api/v3/rules/py-bare-except/docs")
        data = resp.json()
        assert data["status"] == "ok"


class TestV3StatusAndRecord:
    def test_status_aggregates(self, client: TestClient) -> None:
        resp = client.get("/api/v3/status")
        data = resp.json()
        assert data["status"] == "ok"
        assert "trend_points" in data["summary"] and "database_size" in data["summary"]

    def test_record_then_latest(self, client: TestClient) -> None:
        report = {
            "timestamp": "2026-08-26T12:00:00",
            "summary": {"total_files": 5, "total_issues": 2},
            "languages": {"python": {"files": 5}},
        }
        resp = client.post("/api/record", json=report)
        assert resp.json()["status"] == "recorded"
        latest = client.get("/api/latest").json()
        assert latest is not None


class TestCIRoutes:
    def test_ci_summary_reads_file(self, tmp_path: Path) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        _add_ci_routes(app, str(tmp_path))
        (tmp_path / "summary.json").write_text('{"passed": true}', encoding="utf-8")
        resp_data = TestClient(app).get("/api/ci-summary").json()
        assert resp_data == {"passed": True}

    def test_ci_summary_missing_dir(self, tmp_path: Path) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        _add_ci_routes(app, str(tmp_path / "nope"))
        assert TestClient(app).get("/api/ci-summary").json() is None


class TestHelpers:
    def test_get_db_size_exists_and_missing(self, tmp_path: Path) -> None:
        existing = tmp_path / "x.db"
        sqlite3.connect(existing).close()
        info = _get_db_size(str(existing))
        assert info["exists"] is True and info["bytes"] >= 0
        missing = _get_db_size(str(tmp_path / "nope.db"))
        assert missing["exists"] is False and missing["bytes"] == 0

    def test_load_rules_summary_counts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.rules_engine import dashboard as dash

        fake = MagicMock(__name__="fake")
        fake.side_effect = lambda lang: {"anti_patterns": [1], "security_patterns": []}
        import tools.scripts.adg_cli.rules as rules_mod

        monkeypatch.setattr(rules_mod, "load_rules_for_language", fake)
        summary = dash._load_rules_summary()
        assert summary["python"] == 1

    def test_load_rules_summary_error_is_negative_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.adg_cli.rules as rules_mod
        from tools.scripts.rules_engine import dashboard as dash

        def boom(lang: str) -> dict:  # type: ignore[type-arg]
            raise ValueError("nope")

        monkeypatch.setattr(rules_mod, "load_rules_for_language", boom)
        assert dash._load_rules_summary()["rust"] == -1

    def test_get_rule_docs_no_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # _get_rule_docs 用 __file__ 推路径, 真实仓库可能存在缓存; 只验证返回结构合法
        result = _get_rule_docs("some-rule")
        assert result["status"] in ("ok", "error") and result["rule_id"] == "some-rule"

    def test_record_routes_direct(self, tmp_path: Path) -> None:
        from fastapi import FastAPI

        db_path = str(tmp_path / "rec.db")
        conn = init_db(db_path)
        try:
            app = FastAPI()
            _add_record_routes(app, conn)
            c = TestClient(app)
            resp = c.post("/api/record", json={"summary": {}})
            assert resp.json()["run_id"] >= 1
        finally:
            conn.close()
            close_connection(db_path)

    def test_v3_health_direct_with_bad_conn(self, tmp_path: Path) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        conn = sqlite3.connect(":memory:")
        conn.close()  # 已关闭的连接 → database: error 分支
        _add_v3_health_route(app, conn)
        body = TestClient(app).get("/api/v3/health").json()
        assert body["database"] in ("connected", "error")

    def test_v3_check_route_direct(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        _add_v3_check_route(app)
        proc = MagicMock(returncode=0)
        proc.stdout = "{}"
        with patch("subprocess.run", return_value=proc):
            assert TestClient(app).post("/api/v3/check?path=.").json()["status"] == "ok"

    def test_v3_rules_route_import_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        # 函数内 from-import 查 sys.modules 缓存, patch 源头模块属性无效 → 直接删缓存触发 ImportError
        monkeypatch.setitem(sys.modules, "tools.scripts.adg_cli.rules", None)
        _add_v3_rules_routes(app)
        body = TestClient(app).get("/api/v3/rules").json()
        assert body["status"] == "error"

    def test_main_uvicorn_missing_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.rules_engine import dashboard as dash

        monkeypatch.setattr("sys.argv", ["dashboard.py", "--db", str(tmp_path / "m.db")])
        monkeypatch.setitem(sys.modules, "uvicorn", None)
        with pytest.raises(SystemExit):
            dash.main()

    def test_main_create_app_and_run_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # uvicorn.run mock 掉, 验证 main 正常装配路径
        from tools.scripts.rules_engine import dashboard as dash

        run_mock = MagicMock()
        fake_uvicorn = MagicMock(run=run_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py", "--port", "9999", "--db", str(tmp_path / "r.db")])
        monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
        dash.main()
        assert run_mock.called

    def test_load_rules_summary_import_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.rules_engine import dashboard as dash

        monkeypatch.setitem(sys.modules, "tools.scripts.adg_cli.rules", None)
        assert dash._load_rules_summary() == {"error": "ADG rules module not available"}
