"""hooks_runner 第二轮攻坚: doctor/baseline/secret-scan/quality-gate-new/dispatch/main。

覆盖第二轮缺口(27%→70%+):
- _check_pre_commit_hook(未安装/非 pre-commit 生成/坏 Python/探测失败/健康)
- _check_tool_available(可用/不可用必需/可选+hint)
- _doctor_check_plugins / _doctor_check_hooks_json
- _handle_doctor(全过/有失败)
- _handle_baseline_validate/recompute(结构坏/一致/不一致)
- _compare_baseline_with_current(新增/过松)
- _handle_secret_scan(text 有发现/干净/json/sarif/output)
- _handle_quality_gate_new(baseline 存在与否)
- _dispatch(incremental/simple 表/lang 分流/unknown)与 main
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts import hooks_runner as hr


def _args(**kw: object) -> argparse.Namespace:
    base: dict[str, object] = {"path": Path("."), "command": "doctor"}
    base.update(kw)
    return argparse.Namespace(**base)  # type: ignore[arg-type]


# ── pre-commit 钩子检查 ─────────────────────────────────────


class TestCheckPreCommitHook:
    def test_hook_not_installed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        ok, desc = hr._check_pre_commit_hook()
        assert ok and "未安装" in desc

    def test_non_precommit_hook_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        (tmp_path / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\necho hi\n")
        ok, desc = hr._check_pre_commit_hook()
        assert ok and "非 pre-commit" in desc

    def test_bad_install_python(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True)
        hook.write_text("INSTALL_PYTHON=/nonexistent/python\nexec stuff\n")
        ok, desc = hr._check_pre_commit_hook()
        assert not ok and "不存在" in desc

    def test_probe_timeout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        hook_dir = tmp_path / ".git" / "hooks"
        hook_dir.mkdir(parents=True)
        fake_py = tmp_path / "fakepython"
        fake_py.write_text("")
        hook = hook_dir / "pre-commit"
        hook.write_text(f"INSTALL_PYTHON={fake_py}\n")
        with patch.object(hr.subprocess, "run", side_effect=hr.subprocess.TimeoutExpired(cmd="x", timeout=30)):
            ok, desc = hr._check_pre_commit_hook()
        assert not ok and "探测失败" in desc

    def test_probe_module_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        fake_py = tmp_path / "fakepython"
        fake_py.write_text("")
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        hook.write_text(f"INSTALL_PYTHON={fake_py}\n")
        proc = MagicMock(returncode=1)
        with patch.object(hr.subprocess, "run", return_value=proc):
            ok, desc = hr._check_pre_commit_hook()
        assert not ok and "缺少 pre_commit" in desc

    def test_healthy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        fake_py = tmp_path / "fakepython"
        fake_py.write_text("")
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        hook.write_text(f"INSTALL_PYTHON={fake_py}\n")
        proc = MagicMock(returncode=0)
        with patch.object(hr.subprocess, "run", return_value=proc):
            ok, desc = hr._check_pre_commit_hook()
        assert ok and "健康" in desc


class TestCheckToolAvailable:
    def test_available(self) -> None:
        proc = MagicMock(returncode=0)
        with patch.object(hr.subprocess, "run", return_value=proc):
            ok, desc, req = hr._check_tool_available(["tool"], "tool", True)
        assert ok and "✅" in desc and req

    def test_missing_required_with_hint(self) -> None:
        with patch.object(hr.subprocess, "run", side_effect=OSError("gone")):
            ok, desc, _ = hr._check_tool_available(["tool"], "tool", True, hint="pip install tool")
        assert not ok and "pip install" in desc

    def test_missing_optional_passes(self) -> None:
        with patch.object(hr.subprocess, "run", side_effect=OSError("gone")):
            ok, desc, _ = hr._check_tool_available(["tool"], "opt-tool", False)
        assert ok and "⚠️" in desc


class TestDoctorChecks:
    def test_plugins_all_present(self, capsys: pytest.CaptureFixture[str]) -> None:
        hr._doctor_check_plugins()
        assert "pytest-xdist" in capsys.readouterr().out

    def test_hooks_json_ok_and_broken(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        checks: list[tuple[bool, str]] = []
        (tmp_path / ".jcode").mkdir()
        (tmp_path / ".jcode" / "hooks.json").write_text("{}")
        hr._doctor_check_hooks_json(tmp_path, checks)
        assert checks[-1][0] is True

        (tmp_path / ".jcode" / "hooks.json").write_text("{broken")
        hr._doctor_check_hooks_json(tmp_path, checks)
        assert checks[-1][0] is False

    def test_doctor_all_pass(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / ".git").mkdir()  # doctor 会检查 root/.git 存在
        (tmp_path / ".jcode").mkdir()
        # 合法基线结构: version(int) + files{path:{type:message:count>0}}
        baseline = {"version": 1, "files": {"a.py": {"security:hardcoded": 1}}}
        (tmp_path / ".jcode" / "baseline.json").write_text(json.dumps(baseline))
        (tmp_path / ".jcode" / "hooks.json").write_text("{}")
        with (
            patch.object(hr, "_check_pre_commit_hook", return_value=(True, "ok")),
            patch.object(hr, "_doctor_check_toolchain"),
            patch.object(hr, "_doctor_check_plugins"),
            patch.object(hr, "_doctor_check_hooks_json"),
        ):
            rc = hr._handle_doctor(_args(path=tmp_path))
        assert rc == 0 and "全部必需检查通过" in capsys.readouterr().out

    def test_doctor_failure_returns_one(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch.object(hr, "_check_pre_commit_hook", return_value=(False, "bad hook")),
            patch.object(hr, "_doctor_check_toolchain"),
            patch.object(hr, "_doctor_check_plugins"),
            patch.object(hr, "_doctor_check_hooks_json"),
            patch(
                "tools.scripts.hooks.domain_checks.validate_baseline_structure",
                return_value=(False, "missing"),
            ),
        ):
            rc = hr._handle_doctor(_args(path=tmp_path))
        assert rc == 1 and "未通过" in capsys.readouterr().out


# ── baseline ────────────────────────────────────────────────


class TestBaselineHandlers:
    def _good_baseline(self, tmp_path: Path) -> Path:
        good = tmp_path / "good.json"
        good.write_text(json.dumps({"version": 1, "files": {"a.py": {"sec:m": 1}}}))
        return good

    def test_validate_ok_and_fail(self, tmp_path: Path) -> None:
        assert hr._handle_baseline_validate(_args(file=self._good_baseline(tmp_path))) == 0
        bad = tmp_path / "bad.json"
        bad.write_text("not-json")
        assert hr._handle_baseline_validate(_args(file=bad)) == 1

    def test_default_baseline_file_resolution(self) -> None:
        p = hr._baseline_file_for(Path("/repo"), None)
        assert p == Path("/repo/.jcode/baseline.json")
        assert hr._baseline_file_for(Path("/repo"), Path("/x.json")) == Path("/x.json")

    def test_recompute_consistent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        baseline = tmp_path / "b.json"
        counts = {"a.py": {"sec:msg": 2}}
        baseline.write_text(json.dumps({"version": 1, "files": counts}))
        with (
            patch.object(hr, "_count_current_issues", return_value=counts),
            patch("tools.scripts.hooks.domain_checks.validate_baseline_structure", return_value=(True, "ok")),
        ):
            assert hr._handle_baseline_recompute(_args(path=tmp_path, file=baseline)) == 0
        assert "一致" in capsys.readouterr().out

    def test_recompute_structure_invalid(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text("{}")
        with patch(
            "tools.scripts.hooks.domain_checks.validate_baseline_structure",
            return_value=(False, "bad"),
        ):
            assert hr._handle_baseline_recompute(_args(path=tmp_path, file=baseline)) == 1

    def test_recompute_detects_drift(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text(json.dumps({"version": 1, "files": {"a.py": {"s:m": 1}}}))
        current = {"a.py": {"s:m": 3}}
        with (
            patch.object(hr, "_count_current_issues", return_value=current),
            patch("tools.scripts.hooks.domain_checks.validate_baseline_structure", return_value=(True, "ok")),
        ):
            assert hr._handle_baseline_recompute(_args(path=tmp_path, file=baseline)) == 1
        assert "不一致" in capsys.readouterr().out

    def test_compare_directions(self) -> None:
        problems = hr._compare_baseline_with_current({"a.py": {"s": 5}}, {"a.py": {"s": 2}, "new.py": {"t": 1}})
        joined = "\n".join(problems)
        assert "基线过松" in joined and "新增存量" in joined

    def test_compare_clean_when_equal(self) -> None:
        assert hr._compare_baseline_with_current({"a.py": {"s": 1}}, {"a.py": {"s": 1}}) == []


# ── secret scan ─────────────────────────────────────────────


def _scan_result(findings: list) -> MagicMock:
    r = MagicMock()
    r.findings = findings
    r.scan_duration_ms = 12
    r.tools_used = ["trufflehog"]
    r.errors = []
    r.to_json.return_value = '{"findings": []}'
    r.to_sarif.return_value = {"runs": []}
    return r


class TestHandleSecretScan:
    def test_text_clean(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(hr, "scan_secrets", return_value=_scan_result([])):
            rc = hr._handle_secret_scan(
                _args(
                    path=tmp_path, tools=None, workspace=False, history=False, pr_diff=False, format="text", output=None
                )
            )
        assert rc == 0 and "No secrets" in capsys.readouterr().out

    def test_text_with_findings(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        finding = MagicMock(
            severity="high", tool="gitleaks", rule_id="R1", file="a.py", line=3, secret="sk-1234567890abcdef"
        )
        with patch.object(hr, "scan_secrets", return_value=_scan_result([finding])):
            rc = hr._handle_secret_scan(
                _args(
                    path=tmp_path,
                    tools="gitleaks,trufflehog",
                    workspace=True,
                    history=True,
                    pr_diff=False,
                    format="text",
                    output=None,
                )
            )
        assert rc == 1 and "Found 1 secret" in capsys.readouterr().out

    def test_json_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(hr, "scan_secrets", return_value=_scan_result([])):
            hr._handle_secret_scan(
                _args(
                    path=tmp_path, tools=None, workspace=False, history=False, pr_diff=False, format="json", output=None
                )
            )
        assert '"findings"' in capsys.readouterr().out

    def test_sarif_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(hr, "scan_secrets", return_value=_scan_result([])):
            hr._handle_secret_scan(
                _args(
                    path=tmp_path,
                    tools=None,
                    workspace=False,
                    history=False,
                    pr_diff=False,
                    format="sarif",
                    output=None,
                )
            )
        assert '"runs"' in capsys.readouterr().out

    def test_output_file_suppresses_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out = tmp_path / "r.json"
        with patch.object(hr, "scan_secrets", return_value=_scan_result([])):
            hr._handle_secret_scan(
                _args(
                    path=tmp_path, tools=None, workspace=False, history=False, pr_diff=False, format="json", output=out
                )
            )
        assert capsys.readouterr().out == ""


# ── quality-gate-new / dispatch / main ──────────────────────


class TestQualityGateNewAndDispatch:
    def test_quality_gate_new_with_baseline(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text(json.dumps({"files": {}}))
        with (
            patch("tools.scripts.rules_engine.checker.check_directory", return_value=[]),
            patch("tools.scripts.app_config.get_setting", return_value=2),
            patch.object(hr, "run_quality_gate_new") as rq,
        ):
            rc = hr._handle_quality_gate_new(
                _args(path=tmp_path, jobs=None, baseline=baseline, gate="g", format="text", output=None)
            )
        assert rc == 0
        rq.assert_called_once()

    def test_dispatch_incremental_test(self) -> None:
        with patch.object(hr, "_run_simple", return_value=0) as rs:
            rc = hr._dispatch(_args(command="test", incremental=True, lang=None, base="main"))
        assert rc == 0
        rs.assert_called_once()

    def test_dispatch_simple_command_table(self) -> None:
        with (
            patch.dict(hr.__dict__, {"run_lint": lambda: (True, "lint-ok")}),
            patch.object(hr, "_run_simple", return_value=0) as rs,
        ):
            assert hr._dispatch(_args(command="lint")) == 0
        rs.assert_called_once()

    def test_dispatch_lang_on_simple_cmd_still_uses_table(self) -> None:
        """真实行为: lint 在 _SIMPLE_COMMANDS 表中, 即使带 --lang 也先命中 simple 分支。"""
        sentinel = MagicMock(return_value=(True, "simple"))
        with (
            patch.dict(hr.__dict__, {"run_lint": sentinel}),
            patch.object(hr, "_run_simple", return_value=0) as rs,
        ):
            assert hr._dispatch(_args(command="lint", lang="python")) == 0
        passed = rs.call_args.args[0]
        # _dispatch 把 globals 里的 run_lint 原样传入
        assert passed is sentinel or passed() == sentinel()

    def test_dispatch_unknown_cmd_with_multi_dict(self) -> None:
        """非 simple 表命令 + lang 才会走 _MULTI_COMMANDS 分流(防御路径)。"""
        # 用一个不在 simple/handlers 表中的命令名验证 unknown 兜底前不会误入 multi
        with patch.dict(hr._MULTI_COMMANDS, {}):
            assert hr._dispatch(_args(command="nonexistent", lang="python")) == 1

    def test_dispatch_unknown(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert hr._dispatch(_args(command="bogus")) == 1
        assert "Unknown command" in capsys.readouterr().out

    def test_main_invokes_parser_and_dispatch(self) -> None:
        parser = MagicMock()
        parser.parse_args.return_value = _args(command="lint")
        with (
            patch.object(hr, "_build_parser", return_value=parser),
            patch.object(hr, "_dispatch", return_value=7) as disp,
        ):
            assert hr.main() == 7
        disp.assert_called_once()
