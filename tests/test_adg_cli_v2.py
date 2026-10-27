"""Phase 27: Comprehensive tests for adg_cli.py (43% -> 80%)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.adg_cli import (
    _check_pattern,
    _detect_framework,
    _detect_language_from_file,
    _get_rules_path,
    _load_yaml,
    _make_issue,
    _simple_yaml_parse,
    check_directory,
    check_file,
    load_rules_for_language,
)


class TestGetRulesPath:
    def test_error_when_no_rules_found(self, tmp_path: Path) -> None:
        with (
            patch("tools.scripts.adg_cli.core._RULES_PATH", tmp_path / "nope"),
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.cwd", return_value=tmp_path / "cwd"),
        ):
            with pytest.raises(SystemExit):
                _get_rules_path()

    def test_returns_config_path(self, tmp_path: Path) -> None:
        rules = tmp_path / "rules"
        (rules / "languages").mkdir(parents=True)
        with (
            patch("tools.scripts.adg_cli.core._RULES_PATH", rules),
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.cwd", return_value=tmp_path / "cwd"),
        ):
            assert _get_rules_path() == rules

    def test_returns_env_path(self, tmp_path: Path) -> None:
        rules = tmp_path / "env-rules"
        (rules / "languages").mkdir(parents=True)
        with (
            patch("tools.scripts.adg_cli.core._RULES_PATH", tmp_path / "nope"),
            patch.dict("os.environ", {"ADG_RULES_DIR": str(rules)}, clear=True),
            patch("pathlib.Path.cwd", return_value=tmp_path / "cwd"),
        ):
            assert _get_rules_path() == rules

    def test_returns_workspace_path(self, tmp_path: Path) -> None:
        framework = tmp_path / "ai-dev-framework"
        (framework / "languages").mkdir(parents=True)
        with (
            patch("tools.scripts.adg_cli.core._RULES_PATH", tmp_path / "nope"),
            patch.dict("os.environ", {"GITHUB_WORKSPACE": str(tmp_path)}, clear=True),
            patch("pathlib.Path.cwd", return_value=tmp_path / "cwd"),
        ):
            assert _get_rules_path() == framework


class TestDetectFramework:
    def test_package_json_react(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}})
        )
        assert _detect_framework(tmp_path, "javascript") == "react"

    def test_package_json_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{invalid json")
        assert _detect_framework(tmp_path, "javascript") is None

    def test_package_json_dev_deps(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"devDependencies": {"next": "^14.0.0"}}))
        assert _detect_framework(tmp_path, "typescript") == "nextjs"

    def test_requirements_txt_django(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("Django==4.2\n")
        assert _detect_framework(tmp_path, "python") == "django"

    def test_requirements_txt_fastapi(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("fastapi>=0.100\n")
        assert _detect_framework(tmp_path, "python") == "fastapi"

    def test_requirements_txt_os_error(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2\n")
        with patch.object(Path, "read_text", side_effect=OSError("locked")):
            assert _detect_framework(tmp_path, "python") is None

    def test_go_mod_gin(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("require github.com/gin-gonic/gin v1.9\n")
        assert _detect_framework(tmp_path, "go") == "gin"

    def test_go_mod_os_error(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("")
        with patch.object(Path, "read_text", side_effect=OSError("locked")):
            assert _detect_framework(tmp_path, "go") is None

    def test_no_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"lodash": "^4.0"}}))
        assert _detect_framework(tmp_path, "javascript") is None

    def test_pyproject_toml_fastapi(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = ['fastapi']\n")
        assert _detect_framework(tmp_path, "python") == "fastapi"


class TestDetectLanguageFromFile:
    def test_known_extension(self) -> None:
        assert _detect_language_from_file(Path("main.py")) == "python"

    def test_unknown_extension(self) -> None:
        assert _detect_language_from_file(Path("file.xyz")) is None

    def test_case_insensitive(self) -> None:
        assert _detect_language_from_file(Path("File.PY")) == "python"

    def test_typescript(self) -> None:
        assert _detect_language_from_file(Path("app.tsx")) == "typescript"

    def test_rust(self) -> None:
        assert _detect_language_from_file(Path("lib.rs")) == "rust"


class TestLoadYaml:
    def test_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "test.yml"
        f.write_text("anti_patterns:\n- id: test\n  severity: error\n")
        result = _load_yaml(f)
        assert "anti_patterns" in result

    def test_invalid_yaml_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yml"
        f.write_text("{{{{invalid")
        result = _load_yaml(f)
        # Should return empty dict or parsed fallback
        assert isinstance(result, dict)

    def test_import_error_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "test.yml"
        f.write_text("language: python\nanti_patterns:\n- id: x\n  severity: error\n")
        with patch.dict("sys.modules", {"yaml": None}):
            result = _load_yaml(f)
            assert "anti_patterns" in result


class TestSimpleYamlParseExtended:
    def test_version_field(self, tmp_path: Path) -> None:
        f = tmp_path / "v.yml"
        f.write_text("version: '1.0'\nlanguage: python\n")
        result = _simple_yaml_parse(f)
        assert result.get("version") == "1.0"

    def test_fix_replacement_field(self, tmp_path: Path) -> None:
        f = tmp_path / "f.yml"
        f.write_text("anti_patterns:\n- id: r1\n  fix_replacement: 'use safe'\n")
        result = _simple_yaml_parse(f)
        assert result["anti_patterns"][0]["fix_replacement"] == "use safe"

    def test_ignore_case_field(self, tmp_path: Path) -> None:
        f = tmp_path / "i.yml"
        f.write_text("anti_patterns:\n- id: r1\n  ignore_case: true\n")
        result = _simple_yaml_parse(f)
        assert result["anti_patterns"][0]["ignore_case"] is True

    def test_multiline_field(self, tmp_path: Path) -> None:
        f = tmp_path / "m.yml"
        f.write_text("anti_patterns:\n- id: r1\n  multiline: true\n")
        result = _simple_yaml_parse(f)
        assert result["anti_patterns"][0]["multiline"] is True

    def test_comment_lines_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "c.yml"
        f.write_text("# comment\nlanguage: python\n# another comment\n")
        result = _simple_yaml_parse(f)
        assert result["language"] == "python"

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "e.yml"
        f.write_text("\n\nlanguage: python\n\n")
        result = _simple_yaml_parse(f)
        assert result["language"] == "python"

    def test_unknown_fields_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "u.yml"
        f.write_text("anti_patterns:\n- id: r1\n  unknown_field: value\n")
        result = _simple_yaml_parse(f)
        assert "unknown_field" not in result["anti_patterns"][0]

    def test_multiple_rules(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.yml"
        f.write_text("anti_patterns:\n- id: r1\n  severity: error\n- id: r2\n  severity: warning\n")
        result = _simple_yaml_parse(f)
        assert len(result["anti_patterns"]) == 2

    def test_category_field(self, tmp_path: Path) -> None:
        f = tmp_path / "cat.yml"
        f.write_text("anti_patterns:\n- id: r1\n  category: security\n")
        result = _simple_yaml_parse(f)
        assert result["anti_patterns"][0]["category"] == "security"

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yml"
        f.write_text("")
        result = _simple_yaml_parse(f)
        assert result == {"anti_patterns": []}


class TestCheckFileExtended:
    def test_skip_min_js(self, tmp_path: Path) -> None:
        f = tmp_path / "app.min.js"
        f.write_text("eval('bad')")
        issues = check_file(f, {"anti_patterns": []})
        assert issues == []

    def test_skip_min_css(self, tmp_path: Path) -> None:
        f = tmp_path / "style.min.css"
        f.write_text("body {}")
        issues = check_file(f, {"anti_patterns": []})
        assert issues == []

    def test_skip_lock_files(self, tmp_path: Path) -> None:
        f = tmp_path / "package-lock.json"
        f.write_text("{}")
        issues = check_file(f, {"anti_patterns": []})
        assert issues == []

    def test_binary_file_read_error(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\xff")
        issues = check_file(f, {"anti_patterns": []})
        assert issues == []

    def test_comment_line_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("# bare except: pass\n")
        rules = {"anti_patterns": [{"id": "test", "severity": "error", "pattern": "bare except"}]}
        issues = check_file(f, rules)
        assert issues == []

    def test_js_comment_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "test.js"
        f.write_text("// eval('bad')\n")
        rules = {"anti_patterns": [{"id": "test", "severity": "error", "pattern": "eval\\("}]}
        issues = check_file(f, rules)
        assert issues == []

    def test_severity_filter_excludes_lower(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        rules = {
            "anti_patterns": [
                {"id": "e", "severity": "error", "pattern": "x = 1"},
                {"id": "w", "severity": "warning", "pattern": "x = 1"},
                {"id": "i", "severity": "info", "pattern": "x = 1"},
            ]
        }
        issues = check_file(f, rules, severity_filter="warning")
        sevs = {i.severity for i in issues}
        assert "info" not in sevs
        assert "error" in sevs

    def test_no_pattern_field(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        rules = {"anti_patterns": [{"id": "no-pattern", "severity": "error"}]}
        issues = check_file(f, rules)
        assert issues == []

    def test_exclude_patterns_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("bare except: pass\nimport re\n")
        rules = {
            "anti_patterns": [
                {
                    "id": "test",
                    "severity": "error",
                    "pattern": "bare except",
                    "exclude_patterns": [r"import re"],
                }
            ]
        }
        issues = check_file(f, rules)
        assert issues == []

    def test_invalid_regex(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        rules = {"anti_patterns": [{"id": "bad", "severity": "error", "pattern": "[invalid"}]}
        issues = check_file(f, rules)
        # Invalid regex should not crash
        assert isinstance(issues, list)

    def test_multiline_pattern(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = {
            "anti_patterns": [
                {
                    "id": "ml",
                    "severity": "error",
                    "multiline": True,
                    "pattern": r"try:\n.*\nexcept:\n",
                }
            ]
        }
        issues = check_file(f, rules)
        assert len(issues) >= 1

    def test_multiline_pattern_invalid_regex(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\n")
        rules = {
            "anti_patterns": [
                {
                    "id": "ml",
                    "severity": "error",
                    "multiline": True,
                    "pattern": "[invalid",
                }
            ]
        }
        issues = check_file(f, rules)
        assert isinstance(issues, list)

    def test_ignore_case_pattern(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("BARE EXCEPT: pass\n")
        rules = {
            "anti_patterns": [
                {
                    "id": "ic",
                    "severity": "error",
                    "ignore_case": True,
                    "pattern": "bare except",
                }
            ]
        }
        issues = check_file(f, rules)
        assert len(issues) >= 1

    def test_pattern_in_multiline_string(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = {
            "anti_patterns": [
                {
                    "id": "nl",
                    "severity": "error",
                    "multiline": True,
                    "pattern": "try:\\n",
                }
            ]
        }
        issues = check_file(f, rules)
        assert len(issues) >= 1


class TestCheckPattern:
    def test_exclude_patterns_no_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("bare except: pass\n")
        pd = {
            "id": "r",
            "severity": "error",
            "pattern": "bare except",
            "exclude_patterns": ["nomatch"],
        }
        issues = _check_pattern(f, f.read_text(), f.read_text().split("\n"), pd)
        assert len(issues) >= 1


class TestMakeIssue:
    def test_default_values(self) -> None:
        issue = _make_issue(Path("f.py"), 1, 5, {})
        assert issue.rule_id == "unknown"
        assert issue.severity == "warning"
        assert issue.message == "Anti-pattern detected"

    def test_custom_values(self) -> None:
        pd = {
            "id": "x",
            "severity": "error",
            "category": "sec",
            "message": "bad",
            "fix_hint": "fix it",
        }
        issue = _make_issue(Path("f.py"), 10, 3, pd)
        assert issue.rule_id == "x"
        assert issue.fix_hint == "fix it"


class TestCheckDirectory:
    def test_checks_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "good.py").write_text("x = 1\n")
        (tmp_path / "bad.py").write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = load_rules_for_language("python")
        issues = check_directory(tmp_path, rules)
        ids = [i.rule_id for i in issues]
        assert "py-bare-except" in ids

    def test_skips_non_code_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        issues = check_directory(tmp_path, {"anti_patterns": []})
        assert issues == []

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("eval('bad')")
        issues = check_directory(
            tmp_path,
            {"anti_patterns": [{"id": "x", "severity": "error", "pattern": "eval"}]},
        )
        assert issues == []

    def test_severity_filter(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = load_rules_for_language("python")
        issues = check_directory(tmp_path, rules, severity_filter="error")
        assert all(i.severity == "error" for i in issues)
