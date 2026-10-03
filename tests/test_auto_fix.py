"""Tests for auto_fix.py module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tools.scripts.rules_engine.auto_fix import (
    _apply_replacement,
    _flag_only_fixes,
    apply_fixes,
    apply_fixes_to_directory,
    detect_language,
    format_fix_results,
    load_fix_patterns,
)
from tools.scripts.rules_engine.models import FixResult


class TestDetectLanguage:
    """Test language detection from file extensions."""

    def test_python(self):
        assert detect_language(Path("main.py")) == "python"

    def test_javascript(self):
        assert detect_language(Path("app.js")) == "javascript"
        assert detect_language(Path("App.jsx")) == "javascript"

    def test_typescript(self):
        assert detect_language(Path("index.ts")) == "typescript"
        assert detect_language(Path("App.tsx")) == "typescript"

    def test_rust(self):
        assert detect_language(Path("main.rs")) == "rust"

    def test_java(self):
        assert detect_language(Path("Main.java")) == "java"

    def test_unknown(self):
        assert detect_language(Path("README.md")) is None

    def test_empty(self):
        assert detect_language(Path("file")) is None


class TestLoadFixPatterns:
    """Test fix pattern loading."""

    def test_all_patterns(self):
        patterns = load_fix_patterns()
        assert "py-bare-except" in patterns
        "py-eval-exec" in patterns
        assert "js-eval" in patterns
        assert "rust-unwrap" in patterns

    def test_python_only(self):
        patterns = load_fix_patterns("python")
        assert all(k.startswith("py-") for k in patterns)

    def test_javascript_only(self):
        patterns = load_fix_patterns("javascript")
        assert all(k.startswith("js-") for k in patterns)

    def test_unknown_language(self):
        patterns = load_fix_patterns("unknown")
        # Unknown language returns all patterns (no filtering)
        assert len(patterns) > 0


class TestFlagOnlyFixes:
    """Test flag-only fix detection."""

    def test_finds_matches(self):
        content = "eval(user_input)\nx = eval('1+1')"
        results = _flag_only_fixes(Path("test.py"), content, "py-eval-exec", r"\beval\(", "eval detection")
        assert len(results) == 2
        assert results[0].fixed == "[MANUAL FIX REQUIRED]"
        assert results[0].rule_id == "py-eval-exec"

    def test_no_matches(self):
        content = "x = 1\ny = 2"
        results = _flag_only_fixes(Path("test.py"), content, "py-eval-exec", r"\beval\(", "eval detection")
        assert len(results) == 0

    def test_line_numbers(self):
        content = "line1\nline2\neval(x)"
        results = _flag_only_fixes(Path("test.py"), content, "test", r"\beval\(", "test")
        assert results[0].line == 3


class TestApplyReplacement:
    """Test regex replacement application."""

    def test_simple_replacement(self):
        content = "except:"
        new_content, results = _apply_replacement(
            Path("test.py"),
            content,
            content,
            "py-bare-except",
            r"except\s*:",
            "except Exception:",
            "fix bare except",
        )
        assert new_content == "except Exception:"
        assert len(results) == 1
        assert results[0].original == "except:"
        assert results[0].fixed == "except Exception:"

    def test_no_match(self):
        content = "x = 1"
        new_content, results = _apply_replacement(
            Path("test.py"),
            content,
            content,
            "test",
            r"except\s*:",
            "except Exception:",
            "fix",
        )
        assert new_content == content
        assert len(results) == 0

    def test_multiple_matches(self):
        content = "except:\nexcept:"
        new_content, results = _apply_replacement(
            Path("test.py"),
            content,
            content,
            "test",
            r"except\s*:",
            "except Exception:",
            "fix",
        )
        assert new_content == "except Exception:\nexcept Exception:"
        assert len(results) == 2


class TestApplyFixes:
    """Test apply_fixes on real files."""

    def test_bare_except_fix(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("try:\n    x = 1\nexcept:\n    pass\n")
            f.flush()
            fp = Path(f.name)

        try:
            results = apply_fixes(fp, language="python", dry_run=False)
            fixed = fp.read_text()
            assert "except Exception:" in fixed
            assert "except:" not in fixed
            assert any(r.rule_id == "py-bare-except" for r in results)
        finally:
            fp.unlink()

    def test_dry_run_no_change(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("try:\n    x = 1\nexcept:\n    pass\n")
            f.flush()
            fp = Path(f.name)
            original = fp.read_text()

        try:
            results = apply_fixes(fp, language="python", dry_run=True)
            assert fp.read_text() == original
            assert len(results) > 0
        finally:
            fp.unlink()

    def test_fix_ids_filter(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("try:\n    eval('1+1')\nexcept:\n    pass\n")
            f.flush()
            fp = Path(f.name)

        try:
            results = apply_fixes(fp, language="python", fix_ids=["py-bare-except"])
            assert all(r.rule_id == "py-bare-except" for r in results)
        finally:
            fp.unlink()

    def test_unknown_language(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("hello world")
            f.flush()
            fp = Path(f.name)
        try:
            results = apply_fixes(fp)
            assert results == []
        finally:
            fp.unlink()

    def test_nonexistent_file(self):
        results = apply_fixes(Path("/nonexistent/file.py"))
        assert results == []


class TestApplyFixesToDirectory:
    """Test directory-wide auto-fix."""

    def test_fixes_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # ADR-072: 夹具此前写成顶层的 ``except:``, 那**本身就不是
            # 合法 Python** (except 必须跟在 try 之后)。旧实现无条件
            # 写盘, 所以该用例一直是绿的 —— 它实际在验证"把非法文件
            # 改成另一份非法文件"。加了写盘前语法自检后, 夹具必须先是
            # 合法代码, 否则断言的是兜底而非修复能力。
            body = "try:\n    pass\nexcept:\n    pass\n"
            (p / "a.py").write_text(body)
            (p / "b.py").write_text(body)
            (p / "c.txt").write_text(body)

            results = apply_fixes_to_directory(p, dry_run=False, languages=["python"])
            assert len(results) >= 2
            assert "except Exception:" in (p / "a.py").read_text()
            assert "except Exception:" in (p / "b.py").read_text()

    def test_ignores_node_modules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            nm = p / "node_modules" / "pkg"
            nm.mkdir(parents=True)
            (nm / "index.js").write_text("eval('x')")

            results = apply_fixes_to_directory(p)
            assert len(results) == 0

    def test_ignores_pycache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            cache = p / "__pycache__"
            cache.mkdir()
            (cache / "mod.py").write_text("except:\n    pass")

            results = apply_fixes_to_directory(p)
            assert len(results) == 0


class TestFormatFixResults:
    """Test result formatting."""

    def test_empty(self):
        output = format_fix_results([])
        assert output == "No fixes applied."

    def test_text_format(self):
        results = [
            FixResult(
                "a.py",
                "py-bare-except",
                1,
                "except:",
                "except Exception:",
                "fix bare except",
            ),
        ]
        output = format_fix_results(results, format="text")
        assert "a.py" in output
        assert "py-bare-except" in output

    def test_json_format(self):
        import json

        results = [
            FixResult("a.py", "py-bare-except", 1, "except:", "except Exception:", "fix"),
        ]
        output = format_fix_results(results, format="json")
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["rule_id"] == "py-bare-except"
