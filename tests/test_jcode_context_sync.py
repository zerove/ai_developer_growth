"""测试 .jcode/scripts/context-sync.py（此前仅 37% 覆盖）。

ADR-058 明确该文件必须能在**无网络无 LLM** 环境下工作（hook 路径），
因此测试不应依赖任何外部服务。

本轮补测试时发现并修复的真实缺陷（见 TestBareExceptMasking）：
SpecAuditor.audit 判定裸 `except:` 的条件是
`有裸 except 且 没有具体 except`，于是 diff 中只要出现任意一个
`except ValueError:`，所有裸 `except:` 一并放过——实测"2 个裸 except
+ 1 个具体异常"报 0 项违规。

隔离要求：涉及文件系统的路径一律指向 tmp_path；禁止写真实 CONTEXT.md /
ADR.md / SPEC.md。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = ROOT / ".jcode" / "scripts"


@pytest.fixture(scope="module")
def cs():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("jcode_ctx_sync", _SCRIPTS / "context-sync.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def auditor(cs):
    return cs.SpecAuditor(cs.ContextConfig())


# ── ContextConfig ───────────────────────────────────────────────────


class TestContextConfig:
    def test_defaults(self, cs) -> None:
        cfg = cs.ContextConfig()
        assert cfg.context_file == "CONTEXT.md"
        assert cfg.adr_file == "ADR.md"
        assert cfg.spec_file == "SPEC.md"

    def test_update_window_is_bounded(self, cs) -> None:
        """更新记录只追加不裁剪会膨胀到 6300+ 行，故必须有滚动窗口上限。"""
        assert cs.ContextConfig().max_update_entries == 50

    def test_timeouts_positive(self, cs) -> None:
        cfg = cs.ContextConfig()
        assert cfg.test_timeout > 0
        assert cfg.max_retries > 0
        assert cfg.executor_max_workers > 0


# ── ContextSlicer ───────────────────────────────────────────────────


class TestContextSlicer:
    def test_includes_existing_file(self, cs, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("print(1)", encoding="utf-8")
        out = cs.ContextSlicer().slice([str(f)])
        assert "print(1)" in out
        assert str(f) in out

    def test_missing_file_is_labelled_not_raised(self, cs, tmp_path: Path) -> None:
        out = cs.ContextSlicer().slice([str(tmp_path / "nope.py")])
        assert "不存在" in out

    def test_mixed_files(self, cs, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("X", encoding="utf-8")
        out = cs.ContextSlicer().slice([str(f), str(tmp_path / "gone.py")])
        assert "X" in out and "不存在" in out

    def test_empty_list_placeholder(self, cs) -> None:
        assert "无相关上下文" in cs.ContextSlicer().slice([])

    def test_separator_present_for_multiple(self, cs, tmp_path: Path) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        a.write_text("A", encoding="utf-8")
        b.write_text("B", encoding="utf-8")
        out = cs.ContextSlicer().slice([str(a), str(b)])
        assert out.count("===") == 4, "两个文件应各有起止标记"


# ── SpecAuditor ─────────────────────────────────────────────────────


class TestHardcodedSecret:
    @pytest.mark.parametrize(
        "diff",
        ['password = "hunter2"', "secret='abc'", 'API_KEY = "xyz"', 'token = "t"'],
    )
    def test_detects(self, auditor, diff: str) -> None:
        assert any("硬编码密钥" in v for v in auditor.audit(diff, "t"))

    @pytest.mark.parametrize("diff", ["password = None", 'key = f"{x}"', "token = get_token()"])
    def test_clean_forms_not_flagged(self, auditor, diff: str) -> None:
        assert not any("硬编码密钥" in v for v in auditor.audit(diff, "t"))


class TestEvalExec:
    @pytest.mark.parametrize("diff", ["eval(x)", "exec(code)", "result = eval(y)"])
    def test_detects(self, auditor, diff: str) -> None:
        assert any("eval/exec" in v for v in auditor.audit(diff, "t"))

    @pytest.mark.parametrize("diff", ["evaluate(x)", "executor.run()", "eval_value = 1"])
    def test_similar_names_not_flagged(self, auditor, diff: str) -> None:
        assert not any("eval/exec" in v for v in auditor.audit(diff, "t"))


class TestSqlInjection:
    @pytest.mark.parametrize("diff", ['cursor.execute("SELECT " + x)', "db.query(a + b)"])
    def test_detects_concat(self, auditor, diff: str) -> None:
        assert any("SQL" in v for v in auditor.audit(diff, "t"))

    @pytest.mark.parametrize("diff", ['cursor.execute("SELECT 1")', "db.query(sql)"])
    def test_parameterized_not_flagged(self, auditor, diff: str) -> None:
        assert not any("SQL" in v for v in auditor.audit(diff, "t"))


class TestBareExceptMasking:
    """回归防护：早前只要有任意一个具体 except，所有裸 except 都被放过。"""

    def test_lone_bare_except_detected(self, auditor) -> None:
        v = auditor.audit("try:\n    pass\nexcept:\n    pass", "t")
        assert any("未指定异常类型" in x for x in v)

    def test_bare_except_alongside_specific_is_still_detected(self, auditor) -> None:
        """核心回归：1 个具体 except 不得掩盖裸 except。"""
        diff = "try:\n    pass\nexcept:\n    pass\nexcept ValueError:\n    pass"
        v = auditor.audit(diff, "t")
        assert any("未指定异常类型" in x for x in v), f"裸 except 被具体 except 掩盖: {v}"

    def test_multiple_bare_with_specific_all_detected(self, auditor) -> None:
        diff = "except:\n    a\nexcept:\n    b\nexcept ValueError:\n    c"
        v = auditor.audit(diff, "t")
        assert any("未指定异常类型" in x for x in v), f"多个裸 except 被掩盖: {v}"

    def test_only_specific_except_not_flagged(self, auditor) -> None:
        v = auditor.audit("except ValueError:\n    pass", "t")
        assert not any("未指定异常类型" in x for x in v)


# ── ArchitectureGuard ───────────────────────────────────────────────


class TestArchitectureGuard:
    def _long_ok(self) -> str:
        return "详细设计文档。" * 30 + "包含 sub-task JSON 分解。"

    def test_clean_design_passes(self, cs) -> None:
        out = cs.ArchitectureGuard().check_design_drift(self._long_ok(), "t")
        assert "无架构偏移风险" in out

    def test_todo_flagged(self, cs) -> None:
        out = cs.ArchitectureGuard().check_design_drift(self._long_ok() + "\nTODO: 待补", "t")
        assert "TODO/FIXME" in out

    def test_fixme_flagged(self, cs) -> None:
        out = cs.ArchitectureGuard().check_design_drift(self._long_ok() + "\nFIXME: x", "t")
        assert "TODO/FIXME" in out

    def test_too_short_flagged(self, cs) -> None:
        out = cs.ArchitectureGuard().check_design_drift("太短", "t")
        assert "过于简短" in out

    def test_missing_subtask_json_flagged(self, cs) -> None:
        out = cs.ArchitectureGuard().check_design_drift("详细设计文档。" * 30, "t")
        assert "子任务分解" in out

    def test_multiple_issues_all_listed(self, cs) -> None:
        out = cs.ArchitectureGuard().check_design_drift("TODO 短", "t")
        assert out.count("  - ") >= 2, f"应同时报多项: {out}"


# ── 入口与 main 分派 ────────────────────────────────────────────────


class TestMainDispatch:
    def _run(self, cs, *args: str) -> int:
        with patch.object(sys, "argv", ["context-sync.py", *args]):
            with pytest.raises(SystemExit) as exc:
                cs.main()
        return exc.value.code or 0

    def test_no_action_exits_nonzero(self, cs) -> None:
        # argparse 对缺失必填子命令以 2 退出（CLI 用法错误的标准码）
        assert self._run(cs) == 2

    def test_unknown_action_rejected_by_argparse(self, cs) -> None:
        assert self._run(cs, "no-such-action") == 2

    @pytest.mark.parametrize("action", ["sync", "validate", "audit", "evolve"])
    def test_known_actions_are_accepted(self, cs, action: str) -> None:
        """子命令名必须被 argparse 接受（不能是 2 = 用法错误）。"""
        with patch.object(sys, "argv", ["context-sync.py", action]):
            with pytest.raises(SystemExit) as exc:
                cs.main()
        assert exc.value.code != 2, f"子命令 {action} 被 argparse 拒绝"

    def test_wrong_subcommand_name_is_rejected(self, cs) -> None:
        """audit-spec 曾被我误当作合法名；实际合法名为 audit。"""
        assert self._run(cs, "audit-spec") == 2


class TestSpecAuditNonBlocking:
    def test_missing_spec_file_is_non_blocking(self, cs, tmp_path: Path, capsys) -> None:
        """缺 SPEC.md 时跳过而非失败（显式非阻断）。"""
        rc = cs.audit_spec(str(tmp_path / "SPEC.md"))
        assert rc == 0
        assert "跳过" in capsys.readouterr().out

    def test_existing_empty_spec_passes(self, cs, tmp_path: Path) -> None:
        spec = tmp_path / "SPEC.md"
        spec.write_text("# 规范\n", encoding="utf-8")
        assert cs.audit_spec(str(spec)) == 0

    def test_bare_except_in_spec_fails(self, cs, tmp_path: Path) -> None:
        spec = tmp_path / "SPEC.md"
        spec.write_text("代码示例:\n```python\ntry:\n    pass\nexcept:\n    pass\n```\n", encoding="utf-8")
        assert cs.audit_spec(str(spec)) == 1
