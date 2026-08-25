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
    """混合项目：Go 主导 + 少量 Ruby（Ruby 现已有分层规则，加入 scanned）。"""
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

    def test_all_detected_languages_have_rules(self, mixed_project: Path) -> None:
        """12 种语言全部有分层规则：探测到的语言都应进入 scanned 而非 unsupported。"""
        guard = ArchitectureDriftGuard(mixed_project)
        guard.check_layering()
        assert guard.unsupported_languages == []
        assert "go" in guard.scanned_languages
        assert "ruby" in guard.scanned_languages

    def test_unsupported_mechanism_still_guards_future(self) -> None:
        """防静默回归机制仍在：LAYERING_IMPORT_PATTERNS 与 LANGUAGE_EXTENSIONS 键集合一致。"""
        from tools.scripts.architecture_drift_guard import (
            LANGUAGE_EXTENSIONS,
            LAYERING_IMPORT_PATTERNS,
        )

        assert set(LAYERING_IMPORT_PATTERNS.keys()) == set(LANGUAGE_EXTENSIONS.keys()), (
            "分层规则与语言扩展名映射必须一一对应，否则新语言会静默漏检"
        )

    def test_new_language_rules_violations(self, tmp_path: Path) -> None:
        """抽查 kotlin/csharp/ruby 新规则的违规检测。"""
        cases = [
            ("kt", "kotlin", "import org.springframework.web.client.RestTemplate"),
            ("cs", "csharp", "using Microsoft.AspNetCore.Builder;"),
            ("rb", "ruby", 'require "net/http"'),
        ]
        for ext, lang, bad_import in cases:
            proj = tmp_path / f"proj_{lang}"
            (proj / "domain").mkdir(parents=True)
            (proj / "domain" / f"svc.{ext}").write_text(bad_import + "\n", encoding="utf-8")
            guard = ArchitectureDriftGuard(proj)
            violations = guard.check_layering()
            assert any(f"[{lang}]" in v for v in violations), f"{lang} 违规未被识别: {violations}"

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
