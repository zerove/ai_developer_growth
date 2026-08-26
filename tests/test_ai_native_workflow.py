"""jcode_ai_native_workflow 主管道攻坚: 四步流水线全分支 mock。45%→90%+"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scripts.jcode_ai_native_workflow import JCodeAINativeWorkflow


@pytest.fixture
def wf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JCodeAINativeWorkflow:
    """root 指向 tmp; sys.path 注入保持原样(依赖真实 tools/scripts 下的模块)。"""
    monkeypatch.setattr("tools.scripts.jcode_ai_native_workflow.get_project_root", lambda: tmp_path)
    return JCodeAINativeWorkflow()


GOOD_INTENT = "Implement user login API with JWT auth and tests"


class TestStep1DorRouting:
    def test_pass_records_ledger(self, wf: JCodeAINativeWorkflow) -> None:
        wf._init_ledger(GOOD_INTENT)
        assert wf._step1_dor_routing(GOOD_INTENT) is True
        assert wf.ledger is not None
        events = [
            json.loads(line)["event_type"] for line in wf.ledger.ledger_file.read_text(encoding="utf-8").splitlines()
        ]
        assert "STEP_1_COMPLETE" in events

    def test_fail_short_intent(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        wf._init_ledger("short")
        assert wf._step1_dor_routing("short") is False
        out = capsys.readouterr().out
        assert "DoR" in out and "❌" in out

    def test_fail_tbd_marker(self, wf: JCodeAINativeWorkflow) -> None:
        assert wf._step1_dor_routing("Build the TBD feature with proper design") is False

    def test_fail_without_ledger(self, wf: JCodeAINativeWorkflow) -> None:
        # ledger 未初始化时失败路径不崩
        assert wf._step1_dor_routing("short") is False


class TestSteps2to4:
    def test_step2_semantic_arch(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        wf._step2_semantic_arch()
        assert "Step 2/4" in capsys.readouterr().out

    def test_step3_adversarial_scope(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        wf._init_ledger(GOOD_INTENT)
        wf._step3_adversarial_scope(GOOD_INTENT)
        out = capsys.readouterr().out
        assert "Step 3/4" in out and "🛡️" in out

    def test_step4_telemetry(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        wf._step4_telemetry()
        assert "Step 4/4" in capsys.readouterr().out


class TestFullPipeline:
    def test_happy_path_end_to_end(
        self, tmp_path: Path, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert wf.run_full_pipeline(GOOD_INTENT) is True
        out = capsys.readouterr().out
        assert "PIPELINE" in out and "COMPLETED SUCCESSFULLY" in out
        # 台账四步+首尾齐全
        assert wf.ledger is not None
        events = [
            json.loads(line)["event_type"] for line in wf.ledger.ledger_file.read_text(encoding="utf-8").splitlines()
        ]
        for expected in (
            "PIPELINE_START",
            "STEP_1_COMPLETE",
            "STEP_2_COMPLETE",
            "STEP_3_COMPLETE",
            "STEP_4_COMPLETE",
            "PIPELINE_COMPLETE",
        ):
            assert expected in events

    def test_dor_failure_aborts_early(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        assert wf.run_full_pipeline("short") is False
        out = capsys.readouterr().out
        assert "DoR" in out and "COMPLETED SUCCESSFULLY" not in out

    def test_header_footer_printed(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        wf._print_header()
        wf._print_footer()
        out = capsys.readouterr().out
        assert "=" * 70 in out and "✅" in out

    def test_footer_without_ledger(self, wf: JCodeAINativeWorkflow, capsys: pytest.CaptureFixture[str]) -> None:
        wf._print_footer()  # ledger 为 None 不崩
        assert "COMPLETED" in capsys.readouterr().out
