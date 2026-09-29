"""Phase 27: Comprehensive tests for adg_cli.py (43% -> 80%)."""

from __future__ import annotations

import argparse
import json
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.adg_cli import (
    Issue,
    _check_pattern,
    _detect_framework,
    _detect_language_from_file,
    _format_human,
    _format_json,
    _get_rules_path,
    _load_yaml,
    _make_issue,
    _simple_yaml_parse,
    check_directory,
    check_file,
    cmd_check,
    cmd_detect,
    cmd_install_hooks,
    cmd_list_rules,
    load_rules_for_language,
    main,
)

# ── _get_rules_path ────────────────────────────────────────


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


# ── _detect_framework ──────────────────────────────────────


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


# ── _detect_language_from_file ──────────────────────────────


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


# ── _load_yaml ─────────────────────────────────────────────


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


# ── _simple_yaml_parse ─────────────────────────────────────


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


# ── check_file extended ────────────────────────────────────


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


# ────────────────────────────────────────


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


# ── _make_issue ────────────────────────────────────────────


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


# ── check_directory ────────────────────────────────────────


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


# ── _format_human ──────────────────────────────────────────


class TestFormatHuman:
    def test_with_issues(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "f.py", 1, 1, "msg1", "fix1"),
            Issue("r2", "warning", "style", "f.py", 2, 1, "msg2", ""),
        ]
        output = _format_human(issues, "python", "django", 3)
        assert "python" in output
        assert "django" in output
        assert "msg1" in output
        assert "error" in output
        assert "warning" in output

    def test_no_issues(self) -> None:
        output = _format_human([], "python", None, 5)
        assert "All checks passed" in output
        assert "5 files" in output

    def test_with_framework_none(self) -> None:
        output = _format_human([], "rust", None, 1)
        assert "N/A" not in output

    def test_fix_hint_displayed(self) -> None:
        issues = [Issue("r1", "error", "sec", "f.py", 1, 1, "msg", "use safe")]
        output = _format_human(issues, "python", None, 1)
        assert "use safe" in output

    def test_single_file(self) -> None:
        output = _format_human([], "python", None, 1)
        assert "1 file" in output

    def test_info_severity(self) -> None:
        issues = [Issue("r1", "info", "style", "f.py", 1, 1, "msg", "")]
        output = _format_human(issues, "python", None, 1)
        assert "info" in output

    def test_grouping_by_file(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "a.py", 1, 1, "msg1", ""),
            Issue("r2", "error", "sec", "b.py", 1, 1, "msg2", ""),
        ]
        output = _format_human(issues, "python", None, 2)
        assert "a.py" in output
        assert "b.py" in output


# ── _format_json ───────────────────────────────────────────


class TestFormatJson:
    def test_with_issues(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "f.py", 1, 1, "msg1", "fix1"),
            Issue("r2", "warning", "style", "f.py", 2, 1, "msg2", ""),
        ]
        output = _format_json(issues, "python", "django", 3)
        data = json.loads(output)
        assert data["language"] == "python"
        assert data["framework"] == "django"
        assert data["files_checked"] == 3
        assert data["summary"]["error"] == 1
        assert data["summary"]["warning"] == 1

    def test_no_issues(self) -> None:
        output = _format_json([], "rust", None, 5)
        data = json.loads(output)
        assert data["summary"] == {"error": 0, "warning": 0, "info": 0}


# ── cmd_check ──────────────────────────────────────────────


class TestCmdCheck:
    def test_check_file_with_errors(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=False)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = load_rules_for_language("python")
            result = cmd_check(args)
        assert result == 1  # errors found

    def test_check_file_clean(self, tmp_path: Path) -> None:
        f = tmp_path / "good.py"
        f.write_text("x = 1\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=False)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = {"anti_patterns": []}
            result = cmd_check(args)
        assert result == 0

    def test_check_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        args = argparse.Namespace(path=str(tmp_path), lang="python", severity=None, json=False)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = {"anti_patterns": []}
            result = cmd_check(args)
        assert result == 0

    def test_check_json_output(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=True)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = {"anti_patterns": []}
            result = cmd_check(args)
        assert result == 0

    def test_check_unknown_language(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("hello")
        args = argparse.Namespace(path=str(f), lang=None, severity=None, json=False)
        result = cmd_check(args)
        assert result == 1

    def test_check_with_framework(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("x = 1\n")
        (tmp_path / "requirements.txt").write_text("Django==4.2\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=False)
        with (
            patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock_lang,
            patch("tools.scripts.adg_cli.rules.load_framework_rules") as mock_fw,
            patch("tools.scripts.adg_cli.detect.detect_language") as mock_det,
        ):
            mock_lang.return_value = {"anti_patterns": []}
            mock_fw.return_value = {"anti_patterns": []}
            mock_det.return_value = {
                "language": "python",
                "framework": "django",
                "confidence": 0.9,
            }
            result = cmd_check(args)
        assert result == 0


# ── cmd_detect ─────────────────────────────────────────────


class TestCmdDetect:
    def test_detect_python(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        args = argparse.Namespace(path=str(tmp_path), json=False)
        result = cmd_detect(args)
        assert result == 0

    def test_detect_json_output(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        args = argparse.Namespace(path=str(tmp_path), json=True)
        result = cmd_detect(args)
        assert result == 0

    def test_detect_default_path(self, tmp_path: Path) -> None:
        args = argparse.Namespace(path=".", json=False)
        with patch("tools.scripts.adg_cli.detect.detect_language") as mock:
            mock.return_value = {
                "language": "python",
                "framework": None,
                "confidence": 0.9,
            }
            result = cmd_detect(args)
        assert result == 0


# ── cmd_list_rules ─────────────────────────────────────────


class TestCmdListRules:
    def test_list_python_rules(self) -> None:
        args = argparse.Namespace(lang="python", json=False)
        result = cmd_list_rules(args)
        assert result == 0

    def test_list_json_output(self) -> None:
        args = argparse.Namespace(lang="python", json=True)
        result = cmd_list_rules(args)
        assert result == 0

    def test_list_rust_rules(self) -> None:
        args = argparse.Namespace(lang="rust", json=False)
        result = cmd_list_rules(args)
        assert result == 0


# ── cmd_install_hooks ──────────────────────────────────────


class TestCmdInstallHooks:
    def test_install_to_git_repo(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        args = argparse.Namespace(path=str(tmp_path))
        result = cmd_install_hooks(args)
        assert result == 0
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert "ADG" in hook.read_text()

    def test_install_not_git_repo(self, tmp_path: Path) -> None:
        args = argparse.Namespace(path=str(tmp_path))
        result = cmd_install_hooks(args)
        assert result == 1

    def test_install_hook_content(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        args = argparse.Namespace(path=str(tmp_path))
        result = cmd_install_hooks(args)
        assert result == 0
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        content = hook.read_text()
        assert "#!/bin/bash" in content
        assert "ADG" in content
        assert hook.stat().st_mode & 0o755


# ── main CLI ───────────────────────────────────────────────


class TestMainCLI:
    def test_no_command(self) -> None:
        with patch("sys.argv", ["adg"]):
            result = main()
        assert result == 0

    def test_check_subcommand(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "check", str(f), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_detect_subcommand(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        with patch("sys.argv", ["adg", "detect", str(tmp_path)]):
            result = main()
        assert result == 0

    def test_list_rules_subcommand(self) -> None:
        with patch("sys.argv", ["adg", "list-rules", "--lang", "python"]):
            result = main()
        assert result == 0

    def test_install_hooks_subcommand(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        with patch("sys.argv", ["adg", "install-hooks", str(tmp_path)]):
            result = main()
        assert result == 0

    def test_check_json_flag(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "check", str(f), "--lang", "python", "--json"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_detect_json_flag(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        with patch("sys.argv", ["adg", "detect", str(tmp_path), "--json"]):
            result = main()
        assert result == 0

    def test_check_severity_flag(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch(
            "sys.argv",
            ["adg", "check", str(f), "--lang", "python", "--severity", "error"],
        ):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        assert result == 1

    def test_report_clean_code(self, tmp_path: Path) -> None:
        """Test report on clean code passes."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "report", str(f), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_report_with_errors(self, tmp_path: Path) -> None:
        """Test report on code with errors fails."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "report", str(f), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        assert result == 1

    def test_report_json_output(self, tmp_path: Path) -> None:
        """Test report JSON output."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "report", str(f), "--lang", "python", "--json"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_report_with_threshold(self, tmp_path: Path) -> None:
        """Test report with error threshold."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch(
            "sys.argv",
            ["adg", "report", str(f), "--lang", "python", "--error-threshold", "10"],
        ):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        assert result == 0  # Should pass with high threshold

    def test_report_nonexistent_path(self, tmp_path: Path) -> None:
        """Test report on nonexistent path."""
        with patch(
            "sys.argv",
            ["adg", "report", str(tmp_path / "nonexistent"), "--lang", "python"],
        ):
            result = main()
        assert result == 1

    def test_fix_python_bare_except(self, tmp_path: Path) -> None:
        """Test fix Python bare except."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "fix", str(f), "--lang", "python"]):
            result = main()
        assert result == 0
        content = f.read_text()
        assert "except Exception:" in content
        assert "except:" not in content

    def test_fix_javascript_equality(self, tmp_path: Path) -> None:
        """Test fix JavaScript equality operators."""
        f = tmp_path / "app.js"
        f.write_text("if (x == null) {}\nif (y != undefined) {}\n")
        with patch("sys.argv", ["adg", "fix", str(f), "--lang", "javascript"]):
            result = main()
        assert result == 0
        content = f.read_text()
        assert "=== null" in content
        assert "!== undefined" in content

    def test_fix_json_output(self, tmp_path: Path) -> None:
        """Test fix JSON output."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "fix", str(f), "--lang", "python", "--json"]):
            result = main()
        assert result == 0

    def test_fix_nonexistent_path(self, tmp_path: Path) -> None:
        """Test fix on nonexistent path."""
        with patch(
            "sys.argv",
            ["adg", "fix", str(tmp_path / "nonexistent"), "--lang", "python"],
        ):
            result = main()
        assert result == 1

    def test_fix_directory(self, tmp_path: Path) -> None:
        """Test fix on directory."""
        f1 = tmp_path / "test1.py"
        f1.write_text("try:\n    pass\nexcept:\n    pass\n")
        f2 = tmp_path / "test2.py"
        f2.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "fix", str(tmp_path), "--lang", "python"]):
            result = main()
        assert result == 0
        assert "except Exception:" in f1.read_text()
        assert "except Exception:" in f2.read_text()

    def test_install_hooks_pre_push(self, tmp_path: Path) -> None:
        """Test pre-push hook installation."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "hooks").mkdir()
        with patch("sys.argv", ["adg", "install-hooks", str(tmp_path), "--pre-push"]):
            result = main()
        assert result == 0
        assert (tmp_path / ".git" / "hooks" / "pre-push").exists()

    def test_project_config_custom_rules(self, tmp_path: Path) -> None:
        """Test project config with custom rules."""
        # Create project config
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "rules.yml"
        config_file.write_text(
            "anti_patterns:\n"
            "- id: no-print\n"
            "  name: No print\n"
            "  severity: warning\n"
            "  pattern: '\\bprint\\('\n"
            "  message: Use logging\n"
        )

        # Create test file
        test_file = tmp_path / "app.py"
        test_file.write_text("print('hello')\n")

        with patch("sys.argv", ["adg", "check", str(tmp_path), "--lang", "python"]):
            result = main()
        assert result == 0  # warning only, no errors

    def test_project_config_skip_patterns(self, tmp_path: Path) -> None:
        """Test project config skip patterns."""
        # Create project config
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "rules.yml"
        config_file.write_text("skip_patterns:\n- '*.test.py'\n")

        # Create test files
        test_file = tmp_path / "app.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")
        skipped_file = tmp_path / "app.test.py"
        skipped_file.write_text("try:\n    pass\nexcept:\n    pass\n")

        with patch("sys.argv", ["adg", "check", str(tmp_path), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        # Only app.py should be checked, app.test.py should be skipped
        assert result == 1  # error in app.py only


def test_check_sarif_output_e2e(tmp_path, monkeypatch, capsys):
    """check --sarif 应输出合法 SARIF 2.1.0（GitHub Code Scanning 集成契约）。"""
    import json as _json

    target = tmp_path / "bad.py"
    target.write_text("x = eval('1+1')\n", encoding="utf-8")

    from tools.scripts.adg_cli.commands import cmd_check

    args = types.SimpleNamespace(
        path=str(target),
        lang="python",
        severity="info",
        json=False,
        sarif=True,
        framework=None,
        with_docs=False,
        no_trend=True,
        notify=None,
        min_severity=None,
        exclude=None,
    )
    rc = cmd_check(args)
    out = capsys.readouterr().out
    data = _json.loads(out)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["tool"]["driver"]["name"] == "adg"
    assert len(data["runs"][0]["results"]) > 0
    assert rc != 0  # 有 error 级问题时非零退出


def test_fix_smart_e2e(tmp_path, capsys):
    """fix --smart 应经 AutoFixOrchestrator 用 Ruff 修复未用导入。"""
    import json as _json

    target = tmp_path / "messy.py"
    target.write_text("import os\nimport sys\nx = 1\n", encoding="utf-8")

    from tools.scripts.adg_cli.commands import cmd_fix

    args = types.SimpleNamespace(
        path=str(target),
        lang="python",
        json=True,
        smart=True,
    )
    rc = cmd_fix(args)
    out = capsys.readouterr().out
    stats = _json.loads(out)
    assert stats["mode"] == "smart"
    assert stats["errors"] == 0
    assert stats["fixes_applied"] > 0
    assert "import os" not in target.read_text(encoding="utf-8")
    assert rc == 0


def test_fix_regex_mode_unchanged(tmp_path):
    """默认（正则）模式行为保持: py-bare-except 可被修复。"""
    target = tmp_path / "legacy.py"
    target.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    from tools.scripts.adg_cli.fix import fix_file

    result = fix_file(target)
    assert result["errors"] == 0
    assert result["fixed"] >= 1
    assert "except Exception:" in target.read_text(encoding="utf-8")
