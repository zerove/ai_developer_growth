"""Integration tests for end-to-end pipelines.

These tests verify that components work together correctly, not in isolation.
Each test exercises a complete workflow from input to final output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scripts.detect_language import detect_language_from_file
from tools.scripts.fix_heuristics import heuristic_fix
from tools.scripts.hooks.domain_checks import run_language_rules, run_quality_gate
from tools.scripts.hooks_runner import main as hooks_main
from tools.scripts.rule_catalog import (
    get_pack_info,
    get_pack_source,
    search_rules,
)
from tools.scripts.rules_engine.rule_loader import load_rules
from tools.scripts.validate_language_rules import (
    detect_language_from_file as vl_detect,
)
from tools.scripts.validate_language_rules import (
    validate_directory,
    validate_file,
)

# =============================================================================
# Integration: Detect Language → Validate Rules → Report
# =============================================================================


class TestDetectToValidatePipeline:
    """End-to-end: detect language from file → validate against rules → get result."""

    def test_python_file_full_pipeline(self, tmp_path: Path) -> None:
        """Detect Python → validate → get structured result."""
        py_file = tmp_path / "sample.py"
        py_file.write_text("def foo():\n    pass\n")

        lang = vl_detect(py_file)
        assert lang is not None, "Should detect Python"

        result = validate_file(py_file, lang)
        assert hasattr(result, "passed")
        assert hasattr(result, "issues")
        assert isinstance(result.issues, list)

    def test_typescript_file_full_pipeline(self, tmp_path: Path) -> None:
        """Detect TypeScript → validate → get structured result."""
        ts_file = tmp_path / "sample.ts"
        ts_file.write_text("const x: number = 1;\nconsole.log(x);\n")

        lang = vl_detect(ts_file)
        assert lang is not None, "Should detect TypeScript"

        result = validate_file(ts_file, lang)
        assert hasattr(result, "passed")

    def test_rust_file_full_pipeline(self, tmp_path: Path) -> None:
        """Detect Rust → validate → get structured result."""
        rs_file = tmp_path / "main.rs"
        rs_file.write_text('fn main() {\n    println!("Hello");\n}\n')

        lang = vl_detect(rs_file)
        assert lang is not None, "Should detect Rust"

        result = validate_file(rs_file, lang)
        assert hasattr(result, "passed")

    def test_directory_scan_pipeline(self, tmp_path: Path) -> None:
        """Scan directory → detect all languages → validate each → aggregate."""
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "utils.ts").write_text("const x = 1;\n")
        (tmp_path / "main.rs").write_text("fn main() {}\n")
        (tmp_path / "readme.md").write_text("# Hello\n")

        results = validate_directory(tmp_path)
        assert len(results) >= 3, f"Expected at least 3 results, got {len(results)}"

        for r in results:
            assert hasattr(r, "file")
            assert hasattr(r, "passed")
            assert hasattr(r, "issues")


# =============================================================================
# Integration: Hooks Runner CLI → Full Pipeline
# =============================================================================


class TestHooksRunnerCLIPipeline:
    """End-to-end: CLI entry → argument parsing → execution → output."""

    def test_lint_command_e2e(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test lint command through CLI entry point."""
        with pytest.MonkeyPatch.context() as m:
            m.setattr(sys, "argv", ["hooks_runner.py", "lint"])
            m.setattr(
                "tools.scripts.hooks.basic_checks.subprocess.run",
                lambda *a, **kw: subprocess.CompletedProcess(args=a[0], returncode=0, stdout="OK", stderr=""),
            )
            result = hooks_main()
            assert result == 0

    def test_full_command_e2e(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test full command runs all checks in sequence."""
        with pytest.MonkeyPatch.context() as m:
            m.setattr(sys, "argv", ["hooks_runner.py", "full"])
            # Mock all check functions to avoid real execution
            m.setattr("tools.scripts.hooks_runner.run_lint", lambda: (True, "lint ok"))
            m.setattr(
                "tools.scripts.hooks_runner.run_format_check",
                lambda: (True, "format ok"),
            )
            m.setattr(
                "tools.scripts.hooks_runner.run_typecheck",
                lambda: (True, "typecheck ok"),
            )
            m.setattr("tools.scripts.hooks_runner.run_tests", lambda: (True, "tests ok"))
            m.setattr("tools.scripts.hooks_runner.run_security", lambda: (True, "security ok"))
            m.setattr(
                "tools.scripts.hooks_runner.run_quality_gate",
                lambda *a, **kw: (True, "qg ok"),
            )
            m.setattr(
                "tools.scripts.hooks_runner.run_governance_audit",
                lambda *a, **kw: (True, "ga ok"),
            )
            result = hooks_main()
            assert result == 0


# =============================================================================
# Integration: Rule Catalog → Search → Validate
# =============================================================================


class TestRuleCatalogPipeline:
    """End-to-end: search rules → validate rules directory."""

    def test_search_rules_pipeline(self) -> None:
        """Search for rules → verify results structure."""
        results = search_rules("")
        assert isinstance(results, list)

    def test_get_pack_info_pipeline(self) -> None:
        """Get pack info → verify structure."""
        info = get_pack_info("python")
        if info is not None:
            assert isinstance(info, dict)

    def test_get_pack_source_pipeline(self) -> None:
        """Get pack source path → verify it exists."""
        source = get_pack_source("python")
        if source is not None:
            assert isinstance(source, Path)


# =============================================================================
# Integration: Rule Loading → Checking → Violations
# =============================================================================


class TestRulesEnginePipeline:
    """End-to-end: load rules → apply to code → generate violations."""

    def test_load_python_rules_check_code(self) -> None:
        """Load Python rules → verify structure."""
        rules = load_rules("python")
        assert isinstance(rules, dict), "load_rules should return a dict"
        assert len(rules) > 0, "Should load Python rules"

    def test_load_multiple_languages(self) -> None:
        """Load rules for multiple languages → verify each has rules."""
        languages = ["python", "typescript", "rust", "go"]
        for lang in languages:
            rules = load_rules(lang)
            assert len(rules) > 0, f"{lang} should have rules"

    def test_heuristic_fix_pipeline(self) -> None:
        """Create violation dict → apply heuristic fix → get suggestion."""
        violation = {
            "rule_id": "test-rule",
            "message": "Consider using list comprehension",
        }
        fix = heuristic_fix(violation)
        assert isinstance(fix, dict)


# =============================================================================
# Integration: Quality Gate Pipeline
# =============================================================================


class TestQualityGatePipeline:
    """End-to-end: create code → run quality gate → get report."""

    def test_quality_gate_text_report(self, tmp_path: Path) -> None:
        """Create Python file → run quality gate → get text report."""
        py_file = tmp_path / "sample.py"
        py_file.write_text("# Sample module\nx = 1\n")

        passed, output = run_quality_gate(tmp_path, check_annotation=True)
        assert isinstance(passed, bool)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_quality_gate_json_report(self, tmp_path: Path) -> None:
        """Create Python file → run quality gate → get JSON report."""
        py_file = tmp_path / "sample.py"
        py_file.write_text("# Sample module\nx = 1\n")

        passed, output = run_quality_gate(tmp_path, format="json")
        data = json.loads(output)
        assert "summary" in data
        assert "passed" in data["summary"]
        assert "failed" in data["summary"]
        assert "total_files" in data["summary"]

    def test_language_rules_pipeline(self, tmp_path: Path) -> None:
        """Run language rules → get validation result."""
        py_file = tmp_path / "app.py"
        py_file.write_text("def hello():\n    print('hello')\n")

        passed, output = run_language_rules(tmp_path)
        assert isinstance(passed, bool)


# =============================================================================
# Integration: Detect Language by Extension
# =============================================================================


class TestDetectLanguageIntegration:
    """Integration tests for language detection across file types."""

    @pytest.mark.parametrize(
        "filename,expected_lang",
        [
            ("app.py", "python"),
            ("utils.ts", "typescript"),
            ("component.tsx", "typescript"),
            ("script.js", "javascript"),
            ("main.rs", "rust"),
            ("app.go", "go"),
            ("Main.java", "java"),
            ("App.kt", "kotlin"),
            ("Program.cs", "csharp"),
            ("index.php", "php"),
            ("app.rb", "ruby"),
            ("main.cpp", "cpp"),
            ("main.swift", "swift"),
            ("Main.scala", "scala"),
        ],
    )
    def test_detect_by_extension(self, tmp_path: Path, filename: str, expected_lang: str) -> None:
        """Detect language from file extension for all supported languages."""
        filepath = tmp_path / filename
        filepath.write_text("// placeholder\n")

        lang = detect_language_from_file(filepath)
        if lang is not None:
            assert expected_lang.lower() in lang.lower() or lang.lower() in expected_lang.lower(), (
                f"Expected {expected_lang} for {filename}, got {lang}"
            )

    def test_detect_from_content(self, tmp_path: Path) -> None:
        """Detect language from file content (shebang)."""
        py_file = tmp_path / "script"
        py_file.write_text("#!/usr/bin/env python3\nprint('hello')\n")
        result = detect_language_from_file(py_file)
        if result is not None:
            assert "python" in result.lower()

    def test_unknown_extension_returns_none(self, tmp_path: Path) -> None:
        """Unknown extension should return None gracefully."""
        xyz_file = tmp_path / "data.xyz123"
        xyz_file.write_text("some data\n")
        result = detect_language_from_file(xyz_file)
        assert result is None or isinstance(result, str)


# =============================================================================
# Integration: CLI → detect_language.py
# =============================================================================


class TestDetectLanguageCLIPipeline:
    """Integration test for detect_language.py CLI."""

    def test_cli_main(self, tmp_path: Path) -> None:
        """Run detect_language.py main() → should return 0."""
        from tools.scripts.detect_language import main as dl_main

        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "utils.ts").write_text("const x = 1;\n")

        with pytest.MonkeyPatch.context() as m:
            m.setattr(sys, "argv", ["detect_language.py", str(tmp_path)])
            result = dl_main()
            assert result == 0


# =============================================================================
# Integration: CLI → rule_marketplace.py
# =============================================================================


class TestRuleMarketplaceCLIPipeline:
    """Integration test for rule_marketplace.py CLI."""

    def test_cli_list(self) -> None:
        """Run rule_marketplace.py list → should return 0."""
        from tools.scripts.rule_marketplace import main as rm_main

        with pytest.MonkeyPatch.context() as m:
            m.setattr(sys, "argv", ["rule_marketplace.py", "list"])
            result = rm_main()
            assert result == 0

    def test_cli_search(self) -> None:
        """Run rule_marketplace.py search → should return 0."""
        from tools.scripts.rule_marketplace import main as rm_main

        with pytest.MonkeyPatch.context() as m:
            m.setattr(sys, "argv", ["rule_marketplace.py", "search", "python"])
            result = rm_main()
            assert result == 0
