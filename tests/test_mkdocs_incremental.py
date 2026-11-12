"""P-03: MkDocs 增量构建（内容指纹清单 + 未变更跳过）的契约测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.scripts.mkdocs_incremental import (
    MANIFEST_PATH,
    compute_manifest,
    load_manifest,
    main,
    needs_rebuild,
    run_build,
    save_manifest,
    site_exists,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """最小仓库结构: docs/ + mkdocs.yml + site/。"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: demo\n", encoding="utf-8")
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<html></html>", encoding="utf-8")
    return tmp_path


class TestManifest:
    def test_manifest_tracks_docs_and_config(self, repo: Path) -> None:
        manifest = compute_manifest(repo)
        assert "docs/index.md" in manifest
        assert "docs/guide.md" in manifest
        assert "mkdocs.yml" in manifest

    def test_manifest_ignores_unrelated_files(self, repo: Path) -> None:
        (repo / "README.md").write_text("unrelated\n", encoding="utf-8")
        manifest = compute_manifest(repo)
        assert "README.md" not in manifest

    def test_manifest_changes_with_doc_content(self, repo: Path) -> None:
        before = compute_manifest(repo)
        (repo / "docs" / "guide.md").write_text("# Guide v2\n", encoding="utf-8")
        after = compute_manifest(repo)
        assert before["docs/guide.md"] != after["docs/guide.md"]

    def test_manifest_tracks_mkdocstrings_source(self, repo: Path) -> None:
        """mkdocstrings 引用的源码变化 → 清单必须变化（否则 API 文档会陈旧）。"""
        (repo / "pkg").mkdir()
        (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (repo / "pkg" / "models.py").write_text("X = 1\n", encoding="utf-8")
        (repo / "docs" / "api.md").write_text("::: pkg.models\n", encoding="utf-8")

        before = compute_manifest(repo)
        assert "pkg/models.py" in before

        (repo / "pkg" / "models.py").write_text("X = 2\n", encoding="utf-8")
        after = compute_manifest(repo)
        assert before["pkg/models.py"] != after["pkg/models.py"]

    def test_manifest_survives_roundtrip(self, repo: Path) -> None:
        manifest = compute_manifest(repo)
        save_manifest(repo / MANIFEST_PATH, manifest)
        assert load_manifest(repo / MANIFEST_PATH) == manifest

    def test_load_manifest_tolerates_broken_file(self, repo: Path) -> None:
        path = repo / MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert load_manifest(path) == {}


class TestNeedsRebuild:
    def test_no_manifest_needs_rebuild(self, repo: Path) -> None:
        changed, manifest = needs_rebuild(repo, repo / MANIFEST_PATH)
        assert changed is True
        assert manifest

    def test_identical_manifest_no_rebuild(self, repo: Path) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        changed, _manifest = needs_rebuild(repo, repo / MANIFEST_PATH)
        assert changed is False

    def test_changed_doc_needs_rebuild(self, repo: Path) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        (repo / "docs" / "guide.md").write_text("# changed\n", encoding="utf-8")
        changed, _manifest = needs_rebuild(repo, repo / MANIFEST_PATH)
        assert changed is True


class TestMain:
    def test_check_reports_need_rebuild(self, repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--root", str(repo), "--check"])
        assert code == 1
        assert "需要重建" in capsys.readouterr().out

    def test_check_reports_no_rebuild_when_unchanged(self, repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        code = main(["--root", str(repo), "--check"])
        assert code == 0
        assert "无需重建" in capsys.readouterr().out

    def test_build_skipped_when_up_to_date(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        calls: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path = repo) -> int:
            calls.append(command)
            return 0

        monkeypatch.setattr("tools.scripts.mkdocs_incremental.run_build", fake_run)
        code = main(["--root", str(repo), "--build-command", "mkdocs build"])

        assert code == 0
        assert calls == [], "输入未变化时不应触发构建"

    def test_build_runs_when_manifest_differs(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        (repo / "docs" / "guide.md").write_text("# changed\n", encoding="utf-8")
        calls: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path = repo) -> int:
            calls.append(command)
            return 0

        monkeypatch.setattr("tools.scripts.mkdocs_incremental.run_build", fake_run)
        code = main(["--root", str(repo), "--build-command", "mkdocs build"])

        assert code == 0
        assert len(calls) == 1

    def test_build_runs_when_site_missing(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        (repo / "site" / "index.html").unlink()
        calls: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path = repo) -> int:
            calls.append(command)
            return 0

        monkeypatch.setattr("tools.scripts.mkdocs_incremental.run_build", fake_run)
        main(["--root", str(repo), "--build-command", "mkdocs build"])

        assert len(calls) == 1, "产物缺失时必须重建"

    def test_force_always_builds(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        save_manifest(repo / MANIFEST_PATH, compute_manifest(repo))
        calls: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path = repo) -> int:
            calls.append(command)
            return 0

        monkeypatch.setattr("tools.scripts.mkdocs_incremental.run_build", fake_run)
        main(["--root", str(repo), "--force", "--build-command", "mkdocs build"])

        assert len(calls) == 1

    def test_failed_build_returns_code_and_keeps_manifest(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(command: list[str], cwd: Path = repo) -> int:
            return 2

        monkeypatch.setattr("tools.scripts.mkdocs_incremental.run_build", fake_run)
        code = main(["--root", str(repo), "--build-command", "mkdocs build"])

        assert code == 2
        assert not (repo / MANIFEST_PATH).exists(), "构建失败不应写入清单（否则下次会误判为最新）"

    def test_json_output_is_machine_readable(self, repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--root", str(repo), "--check", "--json"])
        payload: dict[str, Any] = json.loads(capsys.readouterr().out)
        assert code == 1
        assert payload["needs_rebuild"] is True
        assert payload["tracked_files"] > 0


class TestHelpers:
    def test_site_exists_detects_artifact(self, repo: Path) -> None:
        assert site_exists(repo) is True
        (repo / "site" / "index.html").unlink()
        assert site_exists(repo) is False

    def test_run_build_returns_exit_code(self, repo: Path) -> None:
        import sys

        code = run_build([sys.executable, "-c", "raise SystemExit(3)"], repo)
        assert code == 3
