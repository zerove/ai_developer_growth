"""测试 .jcode/scripts/ 下由 hooks.json 驱动的 skill 入口脚本。

这些脚本此前零测试覆盖，却直接决定 on_commit / on_pr / on_merge / scheduled
四类 hook 的成败。测试锁定三件事：
1. 契约：action 名与退出码（hooks_runner 依据 returncode 判成败）
2. 分派：action -> 子命令的映射是否正确
3. 不再调用不存在的 CLI 参数（曾经 update_moc 调 --update-moc 必然失败）
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"


def _load(name: str, alias: str):
    """按 importlib 加载带连字符文件名的 skill 脚本。

    脚本内部用 `from _common import ...` 同级导入，必须先把目录放进 sys.path。
    """
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(alias, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def kc():
    return _load("knowledge-curator", "jcode_knowledge_curator")


@pytest.fixture(scope="module")
def mao():
    return _load("multi-agent-orch", "jcode_multi_agent_orch")


# ── knowledge-curator ────────────────────────────────────────────────


class TestKnowledgeCuratorDispatch:
    """hooks.json / registry.json 引用的每个 action 都必须被 main() 认识。

    做法：把对应子函数打桩返回 0，再跑 main()。若 action 不在分派表里，
    main() 会走"未知 action"分支并以 1 退出 —— 断言因此能真实捕获缺失分派。
    """

    ACTIONS = ("scan", "audit", "validate", "sync", "update-moc")

    def _invoke(self, kc, action: str) -> int:
        argv = ["knowledge-curator.py", action]
        if action == "validate":
            argv.append("dummy-case.md")
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as exc:
                kc.main()
        return exc.value.code or 0

    @pytest.mark.parametrize("action", ACTIONS)
    def test_action_is_dispatched(self, kc, action: str) -> None:
        with patch.object(kc, action.replace("-", "_"), return_value=0):
            assert self._invoke(kc, action) == 0, f"action '{action}' 未被 main() 正确分派"

    def test_unknown_action_is_rejected(self, kc, capsys) -> None:
        """反向对照：未知 action 必须以非零退出，且给出提示。"""
        with patch.object(sys, "argv", ["knowledge-curator.py", "no-such-action"]):
            with pytest.raises(SystemExit) as exc:
                kc.main()
        assert exc.value.code == 1
        assert "no-such-action" in capsys.readouterr().out


class TestKnowledgeCuratorCommands:
    def test_scan_invokes_all_strict(self, kc) -> None:
        with patch.object(kc, "run_command", return_value=(0, "ok")) as rc:
            assert kc.scan() == 0
        assert "--all" in rc.call_args[0][0]
        assert "--strict" in rc.call_args[0][0]

    def test_scan_propagates_failure(self, kc) -> None:
        with patch.object(kc, "run_command", return_value=(1, "boom")):
            assert kc.scan() == 1

    def test_audit_invokes_check_all(self, kc) -> None:
        with patch.object(kc, "run_command", return_value=(0, "")) as rc:
            assert kc.audit() == 0
        assert "--check-all" in rc.call_args[0][0]

    def test_validate_passes_path(self, kc, tmp_path: Path) -> None:
        f = tmp_path / "case.md"
        f.write_text("x", encoding="utf-8")
        with patch.object(kc, "run_command", return_value=(0, "")) as rc:
            assert kc.validate(str(f)) == 0
        assert "--path" in rc.call_args[0][0]
        assert str(f) in rc.call_args[0][0]

    def test_update_moc_reports_unimplemented(self, kc, capsys) -> None:
        """曾经调用 link_auditor.py --update-moc（该参数不存在）→ 必然失败。

        现在必须明确报告未实现，而不是静默调用一个不存在的参数。
        """
        with patch.object(kc, "run_command") as rc:
            code = kc.update_moc()
        out = capsys.readouterr().out
        assert code != 0, "未实现的能力不应报告成功"
        assert "尚未实现" in out
        rc.assert_not_called()


class TestKnowledgeCuratorCli:
    def _run(self, kc, *args: str) -> int:
        with patch.object(sys, "argv", ["knowledge-curator.py", *args]):
            with pytest.raises(SystemExit) as exc:
                kc.main()
        return exc.value.code or 0

    def test_validate_without_path_fails(self, kc) -> None:
        """hooks 早期版本就是靠这条必败的；必须有清晰非零退出码。"""
        assert self._run(kc, "validate") == 1

    def test_unknown_action_fails(self, kc) -> None:
        assert self._run(kc, "no-such-action") == 1

    def test_scan_returns_zero_on_success(self, kc) -> None:
        with patch.object(kc, "scan", return_value=0):
            assert self._run(kc, "scan") == 0


# ── multi-agent-orch ─────────────────────────────────────────────────


class TestMultiAgentOrch:
    def test_rejects_unknown_mode(self, mao) -> None:
        """action='run' 曾被 hooks.json 声明，但脚本只认 waterfall/fanout。"""
        with patch.object(sys, "argv", ["multi-agent-orch.py", "run", "req"]):
            with pytest.raises(SystemExit) as exc:
                mao.main()
        assert exc.value.code == 1

    def test_rejects_missing_request(self, mao) -> None:
        with patch.object(sys, "argv", ["multi-agent-orch.py", "fanout"]):
            with pytest.raises(SystemExit) as exc:
                mao.main()
        assert exc.value.code == 1

    def test_fanout_dispatches_to_run_fan_out(self, mao) -> None:
        demo = MagicMock()
        with patch.object(mao, "_load_orch", return_value=demo):
            with patch.object(sys, "argv", ["multi-agent-orch.py", "fanout", "设计评审需求"]):
                mao.main()
        demo.run_fan_out.assert_called_once_with("设计评审需求")
        demo.run_waterfall.assert_not_called()

    def test_waterfall_dispatches_to_run_waterfall(self, mao) -> None:
        demo = MagicMock()
        with patch.object(mao, "_load_orch", return_value=demo):
            with patch.object(sys, "argv", ["multi-agent-orch.py", "waterfall", "重构需求"]):
                mao.main()
        demo.run_waterfall.assert_called_once_with("重构需求")
        demo.run_fan_out.assert_not_called()

    def test_multi_word_request_is_joined(self, mao) -> None:
        demo = MagicMock()
        with patch.object(mao, "_load_orch", return_value=demo):
            with patch.object(sys, "argv", ["multi-agent-orch.py", "fanout", "评审", "当前分支"]):
                mao.main()
        demo.run_fan_out.assert_called_once_with("评审 当前分支")

    def test_uses_example_package_as_source(self, mao) -> None:
        """实现必须来自 examples/multi-agent-orch，而非自带一份。"""
        assert mao.EXAMPLE.name == "multi-agent-orch"
        assert mao.EXAMPLE.parent.name == "examples"
        assert (mao.EXAMPLE / "multi_agent_orch" / "demo.py").exists()


class TestHookCommandSmoke:
    """hooks.json 里指向 multi-agent-orch 的实际命令行必须可解析。"""

    def test_hooks_json_command_is_accepted(self) -> None:
        cfg = (Path(__file__).resolve().parent.parent / ".jcode" / "hooks.json").read_text(encoding="utf-8")
        import json

        hooks = json.loads(cfg)["hooks"]["on_pr"]
        entry = next(h for h in hooks if h["name"] == "multi-agent-design")
        argv = entry["command"].split()[1:]
        assert "waterfall" in argv or "fanout" in argv, f"action 非法: {entry['command']}"
        assert "run" not in argv, f"'run' 不是 multi-agent-orch 支持的 mode: {entry['command']}"

    def test_entry_script_is_executable(self) -> None:
        r = subprocess.run(
            [sys.executable, str(_SCRIPTS / "multi-agent-orch.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert "waterfall" in (r.stdout + r.stderr)
