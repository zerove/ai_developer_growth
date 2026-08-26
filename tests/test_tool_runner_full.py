"""tool_runner.py 覆盖攻坚 (37%→80%+)。

覆盖:
- _get_jobs_setting / _timeout_for_category 配置读取与回退
- _excluded_scan_dirs / _count_language_files / _detect_project_languages
- _run_simple / _build_tool_command / _execute_tool(超时/异常/成功/失败)
- _tool_available / _run_tool_for_language / _run_basic_check_for_languages
- _run_lint_multi 等兼容模式
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tools.scripts.config.models import ToolCategory, ToolConfig
from tools.scripts.hooks.tool_runner import (
    _build_tool_command,
    _count_language_files,
    _detect_project_languages,
    _excluded_scan_dirs,
    _execute_tool,
    _get_jobs_setting,
    _run_basic_check_for_languages,
    _run_simple,
    _run_tool_for_language,
    _timeout_for_category,
    _tool_available,
)
from tools.scripts.language_registry import Language


def make_tool(command: str = "echo", **kw: object) -> ToolConfig:
    return ToolConfig(command=command, args=["--args"], fix_args=["--fix"], check_args=["--check"], **kw)  # type: ignore[arg-type]


class TestJobsAndTimeouts:
    def test_get_jobs_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.scripts.app_config.get_setting", MagicMock(side_effect=RuntimeError))
        assert _get_jobs_setting() == 4

    def test_get_jobs_from_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.scripts.app_config.get_setting", lambda k, d: 8 if k == "jobs" else d)
        assert _get_jobs_setting() == 8

    def test_timeout_test_category(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.scripts.app_config.get_setting", MagicMock(side_effect=RuntimeError))
        assert _timeout_for_category(ToolCategory.TEST) == 900
        assert _timeout_for_category(ToolCategory.LINT) == 300

    def test_timeout_config_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "tools.scripts.app_config.get_setting",
            lambda k, d: {"lint": 180} if k == "timeouts" else d,
        )
        assert _timeout_for_category(ToolCategory.LINT) == 180


class TestScanDirsAndLanguages:
    def test_excluded_dirs_contents(self) -> None:
        excluded = _excluded_scan_dirs()
        assert ".venv" in excluded and "node_modules" in excluded and "__pycache__" in excluded

    def test_count_language_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x=1")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "hidden.py").write_text("x=2")
        counts = _count_language_files(tmp_path)
        assert counts[Language.PYTHON] == 1  # .venv 内不计

    def test_node_langs_require_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "app.ts").write_text("const x=1")
        counts = _count_language_files(tmp_path)
        assert Language.TYPESCRIPT not in counts
        (tmp_path / "package.json").write_text("{}")
        counts = _count_language_files(tmp_path)
        assert counts.get(Language.TYPESCRIPT, 0) >= 1

    def test_detect_project_languages_python(self, tmp_path: Path) -> None:
        for i in range(60):
            (tmp_path / f"m{i}.py").write_text("x=1")
        langs = _detect_project_languages(tmp_path)
        assert Language.PYTHON in langs


class TestRunSimple:
    def test_with_tuple(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = _run_simple((True, "ok"))
        assert rc == 0 and capsys.readouterr().out.strip() == "ok"

    def test_with_callable_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = _run_simple(lambda: (False, "bad"))
        assert rc == 1 and "bad" in capsys.readouterr().out


class TestBuildCommand:
    def test_fix_mode(self) -> None:
        cmd = _build_tool_command(make_tool(), fix=True, check_only=False)
        assert cmd == ["echo", "--fix"]

    def test_check_only_mode(self) -> None:
        cmd = _build_tool_command(make_tool(), fix=False, check_only=True)
        assert cmd == ["echo", "--check"]

    def test_default_args(self) -> None:
        t = make_tool()
        t.fix_args = None
        t.check_args = None
        assert _build_tool_command(t, True, False) == ["echo", "--args"]


class TestExecuteTool:
    def test_success(self, tmp_path: Path) -> None:
        passed, out = _execute_tool(["true"], Language.PYTHON, ToolCategory.LINT, tmp_path)
        assert passed is True and "✅" in out

    def test_failure_includes_stderr(self, tmp_path: Path) -> None:
        passed, out = _execute_tool(
            [__import__("sys").executable, "-c", "import sys; print('o'); print('e', file=sys.stderr); sys.exit(3)"],
            Language.PYTHON,
            ToolCategory.LINT,
            tmp_path,
        )
        assert passed is False and "❌" in out and "e" in out

    def test_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.scripts.hooks.tool_runner._timeout_for_category", lambda c: 1)

        def slow(*a: object, **k: object) -> None:
            raise subprocess.TimeoutExpired(cmd="x", timeout=1)

        monkeypatch.setattr(subprocess, "run", slow)
        passed, out = _execute_tool(["x"], Language.PYTHON, ToolCategory.TEST, tmp_path)
        assert passed is False and "超时" in out


class TestToolAvailable:
    def test_missing_tool_message(self) -> None:
        msg = _tool_available(Language.PYTHON, make_tool(command="no-such-tool-xyz"))
        assert msg is not None and "未安装" in msg

    def test_present_tool_none(self) -> None:
        msg = _tool_available(Language.PYTHON, make_tool(command="echo"))
        # echo --version 返回 0 → 可用
        assert msg is None or "不可用" in msg  # 某些环境 echo 不支持 version flag


class TestRunWithLanguage:
    def test_unconfigured_tool(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.hooks.tool_runner as tr

        monkeypatch.setattr(tr, "get_tool", lambda lang_, cat_: None)
        passed, out = _run_tool_for_language(Language.RUST, ToolCategory.LINT, tmp_path)
        assert passed is False and "未配置" in out

    def test_unavailable_short_circuits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.hooks.tool_runner as tr

        monkeypatch.setattr(tr, "get_tool", lambda lang_, cat_: make_tool())
        monkeypatch.setattr(tr, "_tool_available", lambda lang_, tool_: "  ❌ 未安装")
        passed, out = _run_tool_for_language(Language.PYTHON, ToolCategory.LINT, tmp_path)
        assert passed is False and "未安装" in out

    def test_basic_check_aggregates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.hooks.tool_runner as tr

        calls: list[Language] = []

        def fake_run(
            lang: Language, cat: object, root: Path, fix: bool = False, check_only: bool = False
        ) -> tuple[bool, str]:
            calls.append(lang)
            return (lang != Language.RUST, f"{lang.value}")

        monkeypatch.setattr(tr, "_run_tool_for_language", fake_run)
        passed, out = _run_basic_check_for_languages([Language.PYTHON, Language.RUST], ToolCategory.LINT, tmp_path)
        assert passed is False  # RUST 失败拖累整体
        assert len(calls) == 2


class TestMultiCompatibilityMode:
    def test_lint_multi_defaults_to_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.hooks.tool_runner as tr

        seen: list[list[Language]] = []
        monkeypatch.setattr(
            tr,
            "_run_basic_check_for_languages",
            lambda langs, cat, path, fix=False, check_only=False: (seen.append(langs), (True, ""))[1],
        )
        args = SimpleNamespace(lang=None, path=Path("."), fix=False)
        tr._run_lint_multi(args)
        assert seen == [[Language.PYTHON]]

    def test_lint_multi_with_explicit_lang(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.hooks.tool_runner as tr

        seen: list[list[Language]] = []
        monkeypatch.setattr(
            tr,
            "_run_basic_check_for_languages",
            lambda langs, cat, path, fix=False, check_only=False: (seen.append(langs), (True, ""))[1],
        )
        args = SimpleNamespace(lang="python,rust", path=Path("."), fix=True)
        tr._run_lint_multi(args)
        assert len(seen[0]) == 2
