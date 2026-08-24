"""Tests for dashboard.py module."""

from __future__ import annotations

import pytest

from tools.scripts.rules_engine.dashboard import (
    get_latest_report,
    get_trend_data,
    init_db,
    record_run,
)


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_quality.db")


@pytest.fixture
def conn(db_path):
    """Provide a database connection, closed after test."""
    c = init_db(db_path)
    yield c
    c.close()


class TestInitDb:
    """Test database initialization."""

    def test_creates_tables(self, db_path):
        conn = init_db(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t[0] for t in tables}
        assert "quality_runs" in table_names
        assert "file_results" in table_names
        assert "rule_violations" in table_names
        conn.close()

    def test_idempotent(self, db_path):
        conn1 = init_db(db_path)
        conn1.execute(
            "INSERT INTO quality_runs (timestamp, total_files, total_errors, total_warnings, total_info, passed_files, failed_files, report_json) VALUES ('t', 0, 0, 0, 0, 0, 0, '{}')"
        )
        conn1.commit()
        conn1.close()
        # Second init should work without error
        conn2 = init_db(db_path)
        count = conn2.execute("SELECT COUNT(*) FROM quality_runs").fetchone()[0]
        assert count == 1
        conn2.close()


class TestRecordRun:
    """Test recording quality runs."""

    def test_record_and_retrieve(self, conn):
        report = {
            "summary": {
                "total_files": 10,
                "errors": 2,
                "warnings": 5,
                "info": 3,
                "passed": 8,
                "failed": 2,
            },
            "results": [],
        }
        run_id = record_run(conn, report)
        assert run_id > 0

        latest = get_latest_report(conn)
        assert latest is not None
        assert latest["summary"]["errors"] == 2

    def test_multiple_runs(self, conn):
        for i in range(3):
            report = {
                "summary": {
                    "total_files": 10,
                    "errors": i,
                    "warnings": 0,
                    "info": 0,
                    "passed": 10 - i,
                    "failed": i,
                }
            }
            record_run(conn, report)

        latest = get_latest_report(conn)
        assert latest["summary"]["errors"] == 2


class TestGetTrendData:
    """Test trend data retrieval."""

    def test_empty_trend(self, conn):
        trend = get_trend_data(conn)
        assert trend == []

    def test_trend_data(self, conn):
        report = {
            "summary": {
                "total_files": 10,
                "errors": 1,
                "warnings": 2,
                "info": 0,
                "passed": 9,
                "failed": 1,
            }
        }
        record_run(conn, report)

        trend = get_trend_data(conn)
        assert len(trend) == 1
        assert trend[0]["errors"] == 1

    def test_trend_limit(self, conn):
        for i in range(5):
            report = {
                "summary": {
                    "total_files": 10,
                    "errors": i,
                    "warnings": 0,
                    "info": 0,
                    "passed": 10,
                    "failed": 0,
                }
            }
            record_run(conn, report)

        trend = get_trend_data(conn, limit=3)
        assert len(trend) == 3


class TestCreateApp:
    """Test FastAPI app creation."""

    def test_creates_app(self, db_path):
        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        assert app is not None
        assert app.title == "ADG Quality Dashboard"

    def test_api_endpoints(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        # Dashboard page
        resp = client.get("/")
        assert resp.status_code == 200

        # API trend
        resp = client.get("/api/trend")
        assert resp.status_code == 200
        assert resp.json() == []

        # API latest
        resp = client.get("/api/latest")
        assert resp.status_code == 200

    def test_record_api(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        report = {
            "summary": {
                "total_files": 5,
                "errors": 0,
                "warnings": 1,
                "info": 0,
                "passed": 5,
                "failed": 0,
            }
        }
        resp = client.post("/api/record", json=report)
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

    def test_v3_health_endpoint(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        resp = client.get("/api/v3/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "3.0.0"
        assert "database" in data

    def test_v3_rules_endpoint(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        resp = client.get("/api/v3/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "languages" in data

    def test_v3_rules_with_lang(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        resp = client.get("/api/v3/rules?lang=python")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["language"] == "python"

    def test_v3_status_endpoint(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        # Record a run first so we have data
        report = {
            "summary": {
                "total_files": 5,
                "errors": 0,
                "warnings": 1,
                "info": 0,
                "passed": 5,
                "failed": 0,
            }
        }
        client.post("/api/record", json=report)

        resp = client.get("/api/v3/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "summary" in data

    def test_v3_rule_docs_endpoint_unknown(self, db_path):
        from fastapi.testclient import TestClient

        from tools.scripts.rules_engine.dashboard import create_app

        app = create_app(db_path)
        client = TestClient(app)

        resp = client.get("/api/v3/rules/unknown-rule-xyz/docs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["rule_id"] == "unknown-rule-xyz"
