"""测试 .jcode/scripts/hooks_runner.py（jcode hook 执行引擎）。

注意命名坑：本仓库有两个 hooks_runner.py。
- tools/scripts/hooks_runner.py  -> 由 tests/test_hooks_runner.py 覆盖
- .jcode/scripts/hooks_runner.py  -> 本文件覆盖，此前 0%

实测 .jcode/scripts 整体覆盖率仅 44%，其中本文件 0%：它承载全部 26 个
on_commit / on_pr / on_merge / scheduled hook 的分发，坏了门禁会静默失效。

隔离要求（每个测试都必须遵守）:
- get_project_root -> tmp_path：避免读写真实仓库 hooks.json
- hr.CONFIG_PATH   -> tmp_path：mode_decision.conf 是 git 跟踪文件
- subprocess.run   -> 打桩：run_event_hooks 会真实执行 `git add`
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import acquire_repo_read_lock  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"


def _read_real_hooks_json() -> dict:
    """在跨进程共享读锁下读取**真实**受控的 .jcode/hooks.json。

    必须走这个助手而非直接 read_text: 该文件正被
    test_check_hooks_json_integrity.FailOpenDetectorTest 真改写, 无锁时
    会在写者持有 canary 的窗口里读到半截 JSON 而报 JSONDecodeError
    (ADR-073, 实测 -n 8 下偶发)。
    """
    with acquire_repo_read_lock():
        raw = (_SCRIPTS.parent / "hooks.json").read_text(encoding="utf-8")
    return json.loads(raw)


def _load(alias: str):
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(alias, _SCRIPTS / "hooks_runner.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hr():
    return _load("jcode_hooks_engine")


@pytest.fixture
def isolated(hr, tmp_path: Path):
    """把所有副作用面重定向到 tmp_path，并禁止真实子进程。"""
    with (
        patch.object(hr, "get_project_root", return_value=tmp_path),
        patch.object(hr, "CONFIG_PATH", tmp_path / "mode_decision.conf"),
        patch.object(hr.subprocess, "run") as run,
    ):
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield hr, run


def _write_config(root: Path, hooks: dict) -> None:
    (root / ".jcode").mkdir(parents=True, exist_ok=True)
    (root / ".jcode" / "hooks.json").write_text(json.dumps({"hooks": hooks}, ensure_ascii=False), encoding="utf-8")


def _git_calls(run: MagicMock) -> list[list[str]]:
    return [c[0][0] for c in run.call_args_list if c[0] and c[0][0] and c[0][0][0] == "git"]


# ── files_match_condition（纯逻辑） ─────────────────────────────────


class TestFilesMatchCondition:
    def test_no_condition_always_matches(self, hr) -> None:
        assert hr.files_match_condition(["a.py"], "") is True
        assert hr.files_match_condition(None, "") is True

    def test_unparseable_condition_defaults_to_match(self, hr) -> None:
        """无法解析的条件必须放行，不能静默拦住门禁。"""
        assert hr.files_match_condition(["a.py"], "some_unknown('x')") is True

    @pytest.mark.parametrize(
        ("files", "expected"),
        [
            (["docs/efficiency/ai-sdlc.md"], True),
            (["tools/scripts/x.py"], False),
            ([], False),
            (None, False),
        ],
    )
    def test_substring_condition(self, hr, files, expected: bool) -> None:
        assert hr.files_match_condition(files, "files_contain('docs/efficiency/ai-')") is expected

    def test_glob_pattern(self, hr) -> None:
        cond = "files_contain('*.py')"
        assert hr.files_match_condition(["a/b.py"], cond) is True
        assert hr.files_match_condition(["a/b.md"], cond) is False

    def test_multiple_patterns_are_or(self, hr) -> None:
        cond = "files_contain('.adg/rules.yml') || files_contain('.jcode/hooks.json')"
        assert hr.files_match_condition([".jcode/hooks.json"], cond) is True
        assert hr.files_match_condition(["unrelated.txt"], cond) is False

    def test_empty_list_is_no_match(self, hr) -> None:
        """记录当前语义：空列表 = 不匹配（配合 main() 的显式报错关闭 fail-open）。"""
        assert hr.files_match_condition([], "files_contain('x')") is False


# ── run_hook ────────────────────────────────────────────────────────


class TestRunHook:
    def test_condition_mismatch_skips_and_succeeds(self, isolated, capsys) -> None:
        hr, run = isolated
        hook = {"name": "h", "condition": "files_contain('docs/')", "command": "true"}
        assert hr.run_hook(hook, ["a.py"]) is True
        run.assert_not_called()
        assert "跳过" in capsys.readouterr().out

    def test_command_uses_argv_not_shell(self, isolated) -> None:
        """必须走 shlex.split（argv 列表），不得 shell=True。"""
        hr, run = isolated
        hr.run_hook({"name": "h", "command": "python -c 'print(1)'"}, None)
        args, kwargs = run.call_args
        assert isinstance(args[0], list)
        assert kwargs.get("shell") is None

    def test_nonzero_returncode_is_failure(self, isolated) -> None:
        hr, run = isolated
        run.return_value = MagicMock(returncode=1, stdout="out", stderr="err")
        assert hr.run_hook({"name": "h", "command": "false"}, None) is False

    def test_zero_returncode_is_success(self, isolated) -> None:
        hr, run = isolated
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert hr.run_hook({"name": "h", "command": "true"}, None) is True

    def test_missing_skill_script_fails(self, isolated, capsys) -> None:
        """脚本不存在必须失败，不能静默跳过。"""
        hr, run = isolated
        assert hr.run_hook({"name": "h", "skill": "nope", "action": "scan"}, None) is False
        assert "未找到 skill 脚本" in capsys.readouterr().out
        run.assert_not_called()

    def test_skill_path_passes_action(self, isolated, tmp_path: Path) -> None:
        hr, run = isolated
        script = tmp_path / ".jcode" / "scripts" / "demo.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("print('x')", encoding="utf-8")
        hr.run_hook({"name": "h", "skill": "demo", "action": "scan"}, None)
        assert run.call_args[0][0][-1] == "scan"


# ── _set_mode ───────────────────────────────────────────────────────


class TestSetMode:
    @pytest.mark.parametrize("event", ["on_commit", "on_pr", "on_merge", "scheduled"])
    def test_known_events_enable_high_governance(self, isolated, event: str) -> None:
        hr, _ = isolated
        hr._set_mode(hr.EVENT_MODE_MAP[event])
        text = hr.CONFIG_PATH.read_text(encoding="utf-8")
        assert "governance_level=high" in text
        assert "audit_enabled=true" in text

    def test_unknown_event_does_not_write(self, isolated) -> None:
        hr, _ = isolated
        assert "on_unknown" not in hr.EVENT_MODE_MAP
        assert not hr.CONFIG_PATH.exists()

    def test_write_failure_is_non_blocking(self, hr, tmp_path: Path) -> None:
        """OSError 必须被吞掉：模式切换是辅助功能，不得阻断门禁。

        PosixPath 实例属性只读，无法 patch write_text；改为把 CONFIG_PATH
        指向"文件之下的路径"，写入时抛 NotADirectoryError（OSError 子类）。
        """
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        with (
            patch.object(hr, "get_project_root", return_value=tmp_path),
            patch.object(hr, "CONFIG_PATH", blocker / "mode.conf"),
        ):
            hr._set_mode("quality")

    def test_writes_into_tmp_not_repo(self, isolated) -> None:
        hr, _ = isolated
        hr._set_mode("quality")
        assert str(hr.CONFIG_PATH).startswith(str(hr.get_project_root()))


# ── run_event_hooks ─────────────────────────────────────────────────


class TestRunEventHooks:
    def test_event_without_hooks_returns_zero(self, isolated, capsys) -> None:
        hr, run = isolated
        _write_config(hr.get_project_root(), {"on_commit": []})
        assert hr.run_event_hooks("on_commit", None) == 0
        assert "无 hooks 配置" in capsys.readouterr().out
        run.assert_not_called()

    def test_disabled_hook_is_skipped(self, isolated) -> None:
        hr, run = isolated
        _write_config(hr.get_project_root(), {"on_commit": [{"name": "off", "command": "x", "enabled": False}]})
        assert hr.run_event_hooks("on_commit", None) == 0
        run.assert_not_called()

    def test_failures_are_counted(self, isolated) -> None:
        hr, run = isolated
        run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        _write_config(
            hr.get_project_root(),
            {"on_commit": [{"name": "a", "command": "x"}, {"name": "b", "command": "y"}]},
        )
        assert hr.run_event_hooks("on_commit", None) == 2

    def test_no_git_add_when_targets_absent(self, isolated) -> None:
        hr, run = isolated
        _write_config(hr.get_project_root(), {"on_commit": [{"name": "a", "command": "x"}]})
        hr.run_event_hooks("on_commit", None)
        assert _git_calls(run) == [], f"目标文件不存在时不应调用 git: {_git_calls(run)}"

    def test_auto_stage_only_on_commit(self, isolated, tmp_path: Path) -> None:
        hr, run = isolated
        (tmp_path / "CONTEXT.md").write_text("x", encoding="utf-8")
        _write_config(hr.get_project_root(), {"on_merge": [{"name": "a", "command": "x"}]})
        hr.run_event_hooks("on_merge", None)
        assert _git_calls(run) == [], f"非 on_commit 事件不应触发 git: {_git_calls(run)}"

    def test_auto_stage_runs_git_add_on_commit(self, isolated, tmp_path: Path) -> None:
        hr, run = isolated
        (tmp_path / "CONTEXT.md").write_text("x", encoding="utf-8")
        run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        _write_config(hr.get_project_root(), {"on_commit": [{"name": "a", "command": "x"}]})
        hr.run_event_hooks("on_commit", None)
        assert any(c[:2] == ["git", "add"] for c in _git_calls(run)), _git_calls(run)


# ── load_hooks_config ───────────────────────────────────────────────


class TestLoadHooksConfig:
    def test_missing_config_exits(self, isolated, capsys) -> None:
        hr, _ = isolated
        with pytest.raises(SystemExit) as exc:
            hr.load_hooks_config()
        assert exc.value.code == 1
        assert "未找到 hooks 配置" in capsys.readouterr().out

    def test_valid_config_parsed(self, isolated) -> None:
        hr, _ = isolated
        _write_config(hr.get_project_root(), {"on_commit": [{"name": "a"}]})
        assert hr.load_hooks_config()["hooks"]["on_commit"][0]["name"] == "a"


# ── main：--files fail-open 回归防护 ─────────────────────────────────


class TestMainFilesParsing:
    def test_files_with_no_values_fails_closed(self, isolated, capsys) -> None:
        """回归防护：空 --files 曾使 10 个条件型 hook 全被跳过却仍报成功。"""
        hr, _ = isolated
        _write_config(hr.get_project_root(), {"on_commit": []})
        with patch.object(sys, "argv", ["hooks_runner.py", "on_commit", "--files"]):
            with pytest.raises(SystemExit) as exc:
                hr.main()
        assert exc.value.code == 1
        assert "--files" in capsys.readouterr().out

    def test_files_followed_by_flag_fails_closed(self, isolated) -> None:
        hr, _ = isolated
        with patch.object(sys, "argv", ["hooks_runner.py", "on_commit", "--files", "--verbose"]):
            with pytest.raises(SystemExit) as exc:
                hr.main()
        assert exc.value.code == 1

    def test_files_values_reach_condition_matching(self, isolated) -> None:
        hr, run = isolated
        seen: list = []
        _write_config(
            hr.get_project_root(),
            {"on_commit": [{"name": "a", "command": "x", "condition": "files_contain('*.md')"}]},
        )

        def spy(hook, changed_files=None):
            seen.append(changed_files)
            return True

        with patch.object(hr, "run_hook", side_effect=spy):
            with patch.object(sys, "argv", ["hooks_runner.py", "on_commit", "--files", "a.md"]):
                hr.main()
        assert seen == [["a.md"]]

    def test_no_arguments_exits(self, isolated) -> None:
        hr, _ = isolated
        with patch.object(sys, "argv", ["hooks_runner.py"]):
            with pytest.raises(SystemExit) as exc:
                hr.main()
        assert exc.value.code == 1

    def test_unknown_event_exits(self, isolated, capsys) -> None:
        hr, _ = isolated
        with patch.object(sys, "argv", ["hooks_runner.py", "on_bogus"]):
            with pytest.raises(SystemExit) as exc:
                hr.main()
        assert exc.value.code == 1
        assert "on_bogus" in capsys.readouterr().out

    def test_list_exits_zero(self, isolated, capsys) -> None:
        hr, _ = isolated
        _write_config(hr.get_project_root(), {"on_commit": [{"name": "a", "command": "x"}]})
        with patch.object(sys, "argv", ["hooks_runner.py", "list"]):
            with pytest.raises(SystemExit) as exc:
                hr.main()
        assert exc.value.code == 0
        assert "on_commit" in capsys.readouterr().out

    def test_list_shows_condition(self, isolated, capsys) -> None:
        hr, _ = isolated
        _write_config(
            hr.get_project_root(),
            {"on_commit": [{"name": "a", "command": "x", "condition": "files_contain('*.md')"}]},
        )
        hr.list_hooks()
        assert "files_contain('*.md')" in capsys.readouterr().out

    def test_list_shows_disabled_marker(self, isolated, capsys) -> None:
        hr, _ = isolated
        _write_config(
            hr.get_project_root(),
            {"on_commit": [{"name": "a", "command": "x", "enabled": False}]},
        )
        hr.list_hooks()
        assert "⏸️" in capsys.readouterr().out


# ── 与真实仓库配置的一致性 ──────────────────────────────────────────


class TestRealConfigConsistency:
    """用真实 hooks.json 校验分发契约，防止配置与引擎漂移。

    跨进程共享读锁 (ADR-073): 本类只**读**受控的 .jcode/hooks.json,
    但同文件正被 test_check_hooks_json_integrity.FailOpenDetectorTest 真改写。
    无锁时会在写者持有 canary 的窗口里读到半截 JSON 而报 JSONDecodeError。
    """

    def test_all_condition_forms_are_parseable(self, hr) -> None:
        config = _read_real_hooks_json()
        for event, hooks in config["hooks"].items():
            for hook in hooks:
                cond = hook.get("condition", "")
                if not cond:
                    continue
                assert "files_contain('" in cond, f"{event}/{hook['name']} 条件无法解析: {cond}"

    def test_every_hook_has_name(self, hr) -> None:
        config = _read_real_hooks_json()
        for event, hooks in config["hooks"].items():
            for hook in hooks:
                assert "name" in hook, f"{event} 存在无 name 的 hook"

    def test_every_hook_has_skill_or_command(self, hr) -> None:
        config = _read_real_hooks_json()
        for event, hooks in config["hooks"].items():
            for hook in hooks:
                assert hook.get("command") or hook.get("skill"), (
                    f"{event}/{hook['name']} 既无 command 也无 skill，引擎无法执行"
                )

    def test_referenced_skill_scripts_exist(self, hr) -> None:
        config = _read_real_hooks_json()
        missing = []
        for hooks in config["hooks"].values():
            for hook in hooks:
                skill = hook.get("skill")
                if skill and not hook.get("command"):
                    if not (_SCRIPTS / f"{skill}.py").exists():
                        missing.append(f"{hook['name']} -> {skill}.py")
        assert not missing, f"hooks.json 引用了不存在的脚本: {missing}"
