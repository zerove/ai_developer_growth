"""架构守卫多语言支持测试（M1：消除静默误导）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.architecture_drift_guard import ArchitectureDriftGuard


@pytest.fixture()
def py_project(tmp_path: Path) -> Path:
    """Python 项目：domain 层违规引用 infrastructure。"""
    d = tmp_path / "src" / "domain"
    d.mkdir(parents=True)
    (d / "model.py").write_text("import fastapi\n", encoding="utf-8")
    (tmp_path / "src" / "clean.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def mixed_project(tmp_path: Path) -> Path:
    """混合项目：Go 主导 + 少量 Ruby（Ruby 无分层规则 → unsupported）。"""
    (tmp_path / "cmd").mkdir(parents=True)
    (tmp_path / "internal" / "domain").mkdir(parents=True)
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    (tmp_path / "internal" / "domain" / "svc.go").write_text('package domain\n\nimport "net/http"\n', encoding="utf-8")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "util.rb").write_text("puts 1\n", encoding="utf-8")
    return tmp_path


class TestMultiLanguageLayering:
    def test_python_violation_detected(self, py_project: Path) -> None:
        guard = ArchitectureDriftGuard(py_project)
        violations = guard.check_layering()
        assert len(violations) == 1
        assert "model.py" in violations[0]
        assert "[python]" in violations[0]

    def test_go_violation_detected(self, mixed_project: Path) -> None:
        guard = ArchitectureDriftGuard(mixed_project)
        violations = guard.check_layering()
        assert any("[go]" in v and "net/http" in v for v in violations)

    def test_unsupported_language_reported_not_silent(self, mixed_project: Path) -> None:
        """核心断言：无规则语言必须出现在 unsupported_languages，不得静默跳过。"""
        guard = ArchitectureDriftGuard(mixed_project)
        guard.check_layering()
        assert "ruby" in guard.unsupported_languages
        assert "go" in guard.scanned_languages

    def test_clean_project_zero_violations(self, tmp_path: Path) -> None:
        (tmp_path / "domain").mkdir()
        (tmp_path / "domain" / "a.go").write_text("package domain\n", encoding="utf-8")
        guard = ArchitectureDriftGuard(tmp_path)
        assert guard.check_layering() == []
        assert guard.unsupported_languages == []

    def test_no_source_files_no_crash(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# docs only\n", encoding="utf-8")
        guard = ArchitectureDriftGuard(tmp_path)
        assert guard.check_layering() == []


class TestLanguageDetection:
    def test_detects_multiple_languages(self, mixed_project: Path) -> None:
        guard = ArchitectureDriftGuard(mixed_project)
        langs = guard.detect_project_languages()
        assert "go" in langs and "ruby" in langs

    def test_skips_venv_and_node_modules(self, tmp_path: Path) -> None:
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "junk.py").write_text("x=1\n", encoding="utf-8")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "junk.js").write_text("x=1;\n", encoding="utf-8")
        guard = ArchitectureDriftGuard(tmp_path)
        assert guard.detect_project_languages() == []
