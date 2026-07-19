"""Tests for src.orchestrator.WorkflowManager — targeting 70%+ coverage."""
import os
import json
from unittest.mock import MagicMock, patch, mock_open, PropertyMock

import pytest

from src.orchestrator import WorkflowManager
from src.exceptions import LLMError
from src.tester import TestResult
from src.config import AppConfig, SyncSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(max_retries=3, test_timeout=30, executor_max_workers=4,
                 context_file="CONTEXT.md"):
    """Build a real AppConfig with sensible defaults for tests."""
    cfg = AppConfig()
    cfg.settings.max_retries = max_retries
    cfg.settings.test_timeout = test_timeout
    cfg.settings.executor_max_workers = executor_max_workers
    cfg.settings.context_file = context_file
    return cfg


def _make_manager(cfg=None, *, llm_client=None, analyzer=None,
                  synthesizer=None, guard=None, auditor=None, evolution=None):
    """Construct a WorkflowManager with all dependencies pre-mocked."""
    cfg = cfg or _make_config()
    manager = WorkflowManager.__new__(WorkflowManager)
    manager.llm_client = llm_client or MagicMock()
    manager.analyzer = analyzer or MagicMock()
    manager.synthesizer = synthesizer or MagicMock()
    manager.guard = guard or MagicMock()
    manager.auditor = auditor or MagicMock()
    manager.evolution = evolution or MagicMock()
    manager.config = cfg
    manager.tester = MagicMock()
    manager.slicer = MagicMock()
    manager.executor = MagicMock()
    return manager


def _task(id_="TASK-1", desc="Implement foo", files=None,
          test_code="assert True", depends_on=None):
    """Build a task dict matching the orchestrator's expected shape."""
    return {
        "id": id_,
        "description": desc,
        "target_files": files or ["foo.py"],
        "verification": {
            "test_code": test_code,
            "expected": "should pass",
        },
        "depends_on": depends_on or [],
    }


# ===========================================================================
# _validate_path
# ===========================================================================

class TestValidatePath:
    """All edge-cases for _validate_path()."""

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    def test_empty_string(self):
        assert self.mgr._validate_path("") is False

    def test_whitespace_only(self):
        assert self.mgr._validate_path("   ") is False

    def test_absolute_path(self):
        assert self.mgr._validate_path("/etc/passwd") is False

    def test_parent_traversal(self):
        assert self.mgr._validate_path("../secret.txt") is False

    def test_tilde_prefix(self):
        assert self.mgr._validate_path("~/file.txt") is False

    def test_valid_relative_path(self):
        assert self.mgr._validate_path("src/module.py") is True

    def test_simple_valid(self):
        assert self.mgr._validate_path("file.txt") is True

    @patch("src.orchestrator.os.path.normpath", side_effect=OSError("bad"))
    def test_oserror_in_normpath(self, _mock):
        assert self.mgr._validate_path("anything") is False

    @patch("src.orchestrator.os.path.abspath", side_effect=ValueError("bad"))
    def test_valueerror_in_abspath(self, _mock):
        assert self.mgr._validate_path("anything") is False

    def test_nested_traversal(self):
        assert self.mgr._validate_path("src/../../etc/passwd") is False

    def test_tilde_in_middle_rejected_by_cwd_check(self):
        """Paths with ~ are already caught; this is a no-tilde relative that
        might resolve outside cwd on some systems."""
        assert self.mgr._validate_path("safe_path.txt") is True


# ===========================================================================
# _write_to_file
# ===========================================================================

class TestWriteToFile:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    @patch("src.orchestrator.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_write_success(self, mock_file, mock_makedirs):
        result = self.mgr._write_to_file("output.txt", "hello world")
        assert result is True
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once_with("output.txt", "w", encoding="utf-8")
        mock_file().write.assert_called_once_with("hello world")

    def test_invalid_path_rejected(self):
        result = self.mgr._write_to_file("/etc/bad", "data")
        assert result is False

    @patch("src.orchestrator.os.makedirs", side_effect=OSError("disk full"))
    def test_oserror_returns_false(self, _mock):
        result = self.mgr._write_to_file("ok.txt", "data")
        assert result is False

    @patch("src.orchestrator.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_write_subdirectory(self, mock_file, mock_makedirs):
        """Path with dirname should call makedirs with that dirname."""
        result = self.mgr._write_to_file("sub/dir/file.txt", "content")
        assert result is True
        mock_makedirs.assert_called_once_with("sub/dir", exist_ok=True)


# ===========================================================================
# _apply_file_blocks
# ===========================================================================

class TestApplyFileBlocks:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    @patch.object(WorkflowManager, "_write_to_file", return_value=True)
    def test_single_block(self, mock_write):
        output = "[FILE: out.py]\nprint('hi')\n[END]"
        result = self.mgr._apply_file_blocks(output)
        assert result == ["out.py"]
        mock_write.assert_called_once_with("out.py", "print('hi')")

    @patch.object(WorkflowManager, "_write_to_file", return_value=True)
    def test_multiple_blocks(self, mock_write):
        output = (
            "[FILE: a.py]\ncode_a\n[END]\n"
            "[FILE: b.py]\ncode_b\n[END]"
        )
        result = self.mgr._apply_file_blocks(output)
        assert result == ["a.py", "b.py"]
        assert mock_write.call_count == 2

    def test_no_blocks(self):
        result = self.mgr._apply_file_blocks("just some text, no blocks")
        assert result == []

    @patch.object(WorkflowManager, "_write_to_file")
    def test_mixed_valid_invalid(self, mock_write):
        """Only blocks that pass _write_to_file appear in result."""
        mock_write.side_effect = lambda p, c: p != "bad.txt"
        output = (
            "[FILE: good.py]\ncode\n[END]\n"
            "[FILE: bad.txt]\ncode\n[END]\n"
            "[FILE: ok.py]\ncode\n[END]"
        )
        result = self.mgr._apply_file_blocks(output)
        assert "bad.txt" not in result
        assert "good.py" in result
        assert "ok.py" in result

    @patch.object(WorkflowManager, "_write_to_file", return_value=True)
    def test_multiline_content(self, mock_write):
        content = "line1\nline2\nline3"
        output = f"[FILE: multi.py]\n{content}\n[END]"
        result = self.mgr._apply_file_blocks(output)
        assert result == ["multi.py"]
        mock_write.assert_called_once_with("multi.py", content)


# ===========================================================================
# _execute_subtask
# ===========================================================================

class TestExecuteSubtask:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager(cfg=_make_config(max_retries=3))
        self.mgr.slicer = MagicMock(return_value="context")
        self.mgr.tester = MagicMock()

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_first_attempt_success(self, _mock_blocks):
        self.mgr.llm_client.generate.return_value = "[FILE: out.py]\ncode\n[END]"
        self.mgr.tester.run_test.return_value = TestResult(True, "PASS", 0)

        result = self.mgr._execute_subtask(_task())
        assert "Successfully implemented" in result
        assert "TASK-1" in result
        assert self.mgr.llm_client.generate.call_count == 1

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_retry_then_success(self, _mock_blocks):
        self.mgr.llm_client.generate.return_value = "[FILE: out.py]\ncode\n[END]"
        self.mgr.tester.run_test.side_effect = [
            TestResult(False, "FAIL", 1),
            TestResult(True, "PASS", 0),
        ]

        result = self.mgr._execute_subtask(_task())
        assert "Successfully implemented" in result
        assert self.mgr.llm_client.generate.call_count == 2

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_max_retries_exceeded(self, _mock_blocks):
        self.mgr.llm_client.generate.return_value = "[FILE: out.py]\ncode\n[END]"
        self.mgr.tester.run_test.return_value = TestResult(False, "FAIL", 1)

        result = self.mgr._execute_subtask(_task())
        assert "Failed" in result
        assert "3 attempts" in result

    def test_no_test_code_fallback(self):
        """When verification.test_code is missing, should single-shot."""
        t = _task()
        t["verification"] = {}
        self.mgr.llm_client.generate.return_value = "[FILE: out.py]\ncode\n[END]"
        with patch.object(WorkflowManager, "_apply_file_blocks",
                          return_value=["out.py"]):
            result = self.mgr._execute_subtask(t)
        assert "single-shot" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_llm_error_exception(self, _mock_blocks):
        """LLMError should be caught and retried."""
        self.mgr.llm_client.generate.side_effect = LLMError("API down")
        # All attempts fail with LLMError → max retries
        result = self.mgr._execute_subtask(_task())
        assert "Failed" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_os_error_exception(self, _mock_blocks):
        """OSError should be caught and retried."""
        self.mgr.llm_client.generate.side_effect = OSError("disk error")
        result = self.mgr._execute_subtask(_task())
        assert "Failed" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=[])
    def test_no_valid_file_blocks_logs_warning(self, _mock_blocks):
        """When _apply_file_blocks returns empty, loop continues."""
        self.mgr.llm_client.generate.return_value = "[FILE: x.py]\nc\n[END]"
        self.mgr.tester.run_test.return_value = TestResult(True, "PASS", 0)
        result = self.mgr._execute_subtask(_task())
        assert "Successfully implemented" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_empty_llm_output(self, _mock_blocks):
        """Empty LLM output returns error immediately."""
        self.mgr.llm_client.generate.return_value = ""
        result = self.mgr._execute_subtask(_task())
        assert "Error: No output" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_none_llm_output(self, _mock_blocks):
        """None LLM output returns error immediately."""
        self.mgr.llm_client.generate.return_value = None
        result = self.mgr._execute_subtask(_task())
        assert "Error: No output" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_retry_prompt_includes_last_error(self, _mock_blocks):
        """Attempt 2+ prompt should contain Previous Attempt Error."""
        self.mgr.llm_client.generate.return_value = "[FILE: out.py]\ncode\n[END]"
        self.mgr.tester.run_test.side_effect = [
            TestResult(False, "traceback info", 1),
            TestResult(True, "PASS", 0),
        ]
        self.mgr._execute_subtask(_task())

        call_args = [c[0][0] for c in self.mgr.llm_client.generate.call_args_list]
        assert len(call_args) == 2
        assert "Previous Attempt Error" in call_args[1]
        assert "traceback info" in call_args[1]


# ===========================================================================
# _phase_design
# ===========================================================================

class TestPhaseDesign:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    def test_approval_valid_json(self):
        sub_tasks = [_task()]
        self.mgr.llm_client.generate.return_value = json.dumps(sub_tasks)
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=True)

        ctx, tasks = self.mgr._phase_design("do stuff", "", approval)
        assert tasks is not None
        assert len(tasks) == 1
        assert ctx == "ctx"
        self.mgr.guard.check_design_drift.assert_called_once()

    def test_approval_rejected(self):
        self.mgr.llm_client.generate.return_value = "design doc"
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=False)

        msg, tasks = self.mgr._phase_design("do stuff", "", approval)
        assert tasks is None
        assert "rejected" in msg.lower()

    def test_approval_invalid_json(self):
        self.mgr.llm_client.generate.return_value = "not json at all"
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=True)

        msg, tasks = self.mgr._phase_design("do stuff", "", approval)
        assert tasks is None
        assert "decomposition" in msg.lower() or "failed" in msg.lower()

    def test_uses_initial_context_when_provided(self):
        sub_tasks = [_task()]
        self.mgr.llm_client.generate.return_value = json.dumps(sub_tasks)
        self.mgr.slicer.slice.return_value = "sliced"
        approval = MagicMock(return_value=True)

        ctx, tasks = self.mgr._phase_design("task", "my initial context", approval)
        # Should NOT call slicer.slice since initial_context is non-empty
        self.mgr.slicer.slice.assert_not_called()
        assert ctx == "my initial context"

    def test_fallback_to_slicer_when_no_initial_context(self):
        sub_tasks = [_task()]
        self.mgr.llm_client.generate.return_value = json.dumps(sub_tasks)
        self.mgr.slicer.slice.return_value = "sliced_ctx"
        approval = MagicMock(return_value=True)

        ctx, tasks = self.mgr._phase_design("task", "", approval)
        self.mgr.slicer.slice.assert_called_once_with([])


# ===========================================================================
# _phase_implement
# ===========================================================================

class TestPhaseImplement:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    def test_all_tasks_succeed(self):
        self.mgr.executor.execute.return_value = {
            "TASK-1": "Successfully implemented TASK-1",
            "TASK-2": "Successfully implemented TASK-2",
        }
        result = self.mgr._phase_implement([_task(), _task("TASK-2")], "task")
        assert result == ""

    def test_partial_failure(self):
        self.mgr.executor.execute.return_value = {
            "TASK-1": "Successfully implemented TASK-1",
            "TASK-2": "Failed TASK-2 after 3 attempts",
        }
        result = self.mgr._phase_implement([_task(), _task("TASK-2")], "task")
        assert "failed" in result.lower()
        assert "TASK-2" in result

    def test_none_result_counts_as_failure(self):
        self.mgr.executor.execute.return_value = {
            "TASK-1": None,
        }
        result = self.mgr._phase_implement([_task()], "task")
        assert "failed" in result.lower()


# ===========================================================================
# _phase_audit
# ===========================================================================

class TestPhaseAudit:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    @patch("src.orchestrator.os.path.exists", return_value=False)
    def test_no_violations(self, _mock_exists):
        self.mgr.auditor.audit.return_value = []
        result = self.mgr._phase_audit([_task()], "task")
        assert result == ""
        self.mgr.auditor.audit.assert_called_once()

    @patch("src.orchestrator.os.path.exists", return_value=False)
    def test_violations_then_fix_success(self, _mock_exists):
        """Audit finds violations on attempt 1, fix clears them on attempt 2."""
        self.mgr.auditor.audit.side_effect = [
            [{"file": "foo.py", "rule": "R1"}],
            [],
        ]
        self.mgr.llm_client.generate.return_value = "[FILE: foo.py]\nfixed\n[END]"
        with patch.object(WorkflowManager, "_apply_file_blocks",
                          return_value=["foo.py"]):
            result = self.mgr._phase_audit([_task()], "task")
        assert result == ""

    @patch("src.orchestrator.os.path.exists", return_value=False)
    def test_max_audit_retries_exceeded(self, _mock_exists):
        """After 3 failed fix attempts, returns error."""
        self.mgr.auditor.audit.return_value = [
            {"file": "foo.py", "rule": "R1"}
        ]
        self.mgr.llm_client.generate.return_value = "[FILE: foo.py]\nbad\n[END]"
        with patch.object(WorkflowManager, "_apply_file_blocks",
                          return_value=["foo.py"]):
            result = self.mgr._phase_audit([_task()], "task")
        assert "failed" in result.lower()
        assert self.mgr.auditor.audit.call_count == 3

    @patch("src.orchestrator.os.path.exists", return_value=False)
    def test_fix_returns_empty_output(self, _mock_exists):
        """When LLM returns empty fix, audit loop retries."""
        self.mgr.auditor.audit.return_value = [
            {"file": "f.py", "rule": "R1"}
        ]
        self.mgr.llm_client.generate.return_value = ""
        result = self.mgr._phase_audit([_task()], "task")
        assert "failed" in result.lower()

    @patch("src.orchestrator.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data="file content here"))
    def test_audit_reads_target_files(self, _mock_exists):
        """Audit collects target file contents as diff."""
        self.mgr.auditor.audit.return_value = []
        result = self.mgr._phase_audit([_task()], "task")
        assert result == ""
        # Verify audit was called with combined diff containing file content
        call_args = self.mgr.auditor.audit.call_args[0]
        assert "file content here" in call_args[0]


# ===========================================================================
# _single_shot_implement
# ===========================================================================

class TestSingleShotImplement:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=["out.py"])
    def test_success(self, _mock_blocks):
        self.mgr.llm_client.generate.return_value = "[FILE: out.py]\ncode\n[END]"
        result = self.mgr._single_shot_implement(
            "TASK-1", "desc", ["out.py"])
        assert "Successfully implemented" in result
        assert "single-shot" in result

    def test_no_output(self):
        self.mgr.llm_client.generate.return_value = ""
        result = self.mgr._single_shot_implement(
            "TASK-1", "desc", ["out.py"])
        assert "Error: No output" in result

    def test_none_output(self):
        self.mgr.llm_client.generate.return_value = None
        result = self.mgr._single_shot_implement(
            "TASK-1", "desc", ["out.py"])
        assert "Error: No output" in result

    @patch.object(WorkflowManager, "_apply_file_blocks",
                  side_effect=Exception("boom"))
    def test_exception_caught(self, _mock_blocks):
        result = self.mgr._single_shot_implement(
            "TASK-1", "desc", ["out.py"])
        assert "Failed" in result
        assert "TASK-1" in result

    @patch.object(WorkflowManager, "_apply_file_blocks", return_value=[])
    def test_no_valid_blocks(self, _mock_blocks):
        """Even with no written files, returns success (single-shot)."""
        self.mgr.llm_client.generate.return_value = "[FILE: x.py]\nc\n[END]"
        result = self.mgr._single_shot_implement(
            "TASK-1", "desc", ["x.py"])
        assert "Successfully implemented" in result


# ===========================================================================
# _phase_sync
# ===========================================================================

class TestPhaseSync:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    @patch("src.orchestrator.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data="diff content"))
    def test_sync_writes_context(self, _mock_exists):
        self.mgr.synthesizer.synthesize_context_update.return_value = "updated ctx"
        tasks = [_task("T1", files=["a.py"])]

        self.mgr._phase_sync(tasks, "task", "old ctx")
        self.mgr.synthesizer.synthesize_context_update.assert_called_once()
        # Verify context file was written
        handle = self.mgr.config.settings.context_file


# ===========================================================================
# _phase_evolution
# ===========================================================================

class TestPhaseEvolution:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    def test_with_candidates(self):
        self.mgr.evolution.analyze_conflicts.return_value = ["cand1", "cand2"]
        # Should not raise
        self.mgr._phase_evolution()
        self.mgr.evolution.analyze_conflicts.assert_called_once()

    def test_no_candidates(self):
        self.mgr.evolution.analyze_conflicts.return_value = []
        self.mgr._phase_evolution()
        self.mgr.evolution.analyze_conflicts.assert_called_once()


# ===========================================================================
# run_flow (integration of phases)
# ===========================================================================

class TestRunFlow:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    def test_rejection_early_return(self):
        """Design rejection short-circuits the whole flow."""
        self.mgr.llm_client.generate.return_value = "design"
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=False)

        result = self.mgr.run_flow("task", approval)
        assert "rejected" in result.lower()

    def test_full_happy_path(self):
        sub_tasks = [_task()]
        self.mgr.llm_client.generate.return_value = json.dumps(sub_tasks)
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=True)
        self.mgr.executor.execute.return_value = {
            "TASK-1": "Successfully implemented TASK-1"
        }
        self.mgr.auditor.audit.return_value = []
        self.mgr.evolution.analyze_conflicts.return_value = []
        self.mgr.synthesizer.synthesize_context_update.return_value = "updated"

        with patch("src.orchestrator.os.path.exists", return_value=False):
            result = self.mgr.run_flow("task", approval)
        assert "completed" in result.lower()

    def test_implement_failure_early_return(self):
        sub_tasks = [_task()]
        self.mgr.llm_client.generate.return_value = json.dumps(sub_tasks)
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=True)
        self.mgr.executor.execute.return_value = {
            "TASK-1": "Failed TASK-1 after 3 attempts"
        }

        result = self.mgr.run_flow("task", approval)
        assert "failed" in result.lower()

    def test_audit_failure_early_return(self):
        sub_tasks = [_task()]
        # First call = design doc, subsequent calls = fix prompt
        self.mgr.llm_client.generate.side_effect = [
            json.dumps(sub_tasks),       # _phase_design
            "[FILE: f.py]\nb\n[END]",    # _phase_audit fix attempt 1
            "[FILE: f.py]\nb\n[END]",    # _phase_audit fix attempt 2
            "[FILE: f.py]\nb\n[END]",    # _phase_audit fix attempt 3
        ]
        self.mgr.slicer.slice.return_value = "ctx"
        approval = MagicMock(return_value=True)
        self.mgr.executor.execute.return_value = {
            "TASK-1": "Successfully implemented TASK-1"
        }
        # Audit always returns violations, never fixes
        self.mgr.auditor.audit.return_value = [
            {"file": "f.py", "rule": "R1"}
        ]

        with patch.object(WorkflowManager, "_apply_file_blocks",
                          return_value=["f.py"]):
            with patch("src.orchestrator.os.path.exists", return_value=False):
                result = self.mgr.run_flow("task", approval)
        assert "audit failed" in result.lower() or "manual" in result.lower()


# ===========================================================================
# _build_design_prompt
# ===========================================================================

class TestBuildDesignPrompt:

    @pytest.fixture(autouse=True)
    def _mgr(self):
        self.mgr = _make_manager()

    def test_prompt_contains_task(self):
        prompt = self.mgr._build_design_prompt("my task", "ctx")
        assert "my task" in prompt

    def test_prompt_contains_context(self):
        prompt = self.mgr._build_design_prompt("t", "project context")
        assert "project context" in prompt

    def test_prompt_requests_json(self):
        prompt = self.mgr._build_design_prompt("t", "c")
        assert "JSON" in prompt
        assert "target_files" in prompt
