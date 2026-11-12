"""本地 CI 镜像（tools/scripts/local_ci_mirror.py）的契约测试。

契约：
- 门禁清单必须覆盖远端 workflow 的核心 job，且与远端 job 一一对应（有 note 说明）；
- 缺工具的门禁必须 **SKIP 并显式说明"未执行，非通过"**，不得静默当通过；
- 门禁失败 → 汇总失败；仅告警门禁（如 ci-heartbeat）失败不阻断；
- 未知门禁名 → 显式报错（退出码 2），不静默忽略。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scripts.local_ci_mirror import (
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    Gate,
    GateRegistry,
    build_registry,
    main,
    run_gate,
    summarize,
)

EXPECTED_GATES = {
    "lint",
    "format",
    "typecheck",
    "test",
    "quality-gate",
    "baseline",
    "governance-audit",
    "docs-validate",
    "link-audit",
    "case-study",
    "tool-matrix",
    "agent-validation",
    "semantic-graph",
    "arch-guard",
    "secret-scan",
    "sbom",
    "dep-graph",
    "ci-heartbeat",
}


class TestRegistry:
    def test_registry_covers_core_remote_jobs(self) -> None:
        registry = build_registry()
        assert set(registry.names()) == EXPECTED_GATES

    def test_every_gate_has_note(self) -> None:
        """每个门禁都要说明它对应哪个远端 job（便于核对覆盖度）。"""
        for gate in build_registry().gates:
            assert gate.note.strip(), f"门禁缺少说明: {gate.name}"

    def test_select_only_and_skip(self) -> None:
        registry = build_registry()
        assert [g.name for g in registry.select(["lint", "format"], [])] == ["lint", "format"]
        selected = registry.select([], ["lint", "format"])
        assert "lint" not in [g.name for g in selected]
        assert "format" not in [g.name for g in selected]

    def test_select_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="未知门禁"):
            build_registry().select(["no-such-gate"], [])


class TestRunGate:
    def test_passing_gate(self, tmp_path: Path) -> None:
        import sys

        gate = Gate("ok", (sys.executable, "-c", "pass"))
        result = run_gate(gate, tmp_path)
        assert result.status == STATUS_PASSED

    def test_failing_gate(self, tmp_path: Path) -> None:
        import sys

        gate = Gate("bad", (sys.executable, "-c", "raise SystemExit(3)"))
        result = run_gate(gate, tmp_path)
        assert result.status == STATUS_FAILED
        assert "exit=3" in result.detail

    def test_missing_tool_is_skipped_not_passed(self, tmp_path: Path) -> None:
        """缺工具 → SKIP 且明说未执行（不能冒充通过）。"""
        gate = Gate(
            "needs-tool", ("definitely-not-installed-tool-xyz",), requires=("definitely-not-installed-tool-xyz",)
        )
        result = run_gate(gate, tmp_path)
        assert result.status == STATUS_SKIPPED
        assert "未执行" in result.detail
        assert result.status != STATUS_PASSED


class TestSummarize:
    def test_failure_blocks(self) -> None:
        from tools.scripts.local_ci_mirror import GateResult

        summary = summarize([GateResult("a", STATUS_FAILED)])
        assert summary["ok"] is False
        assert summary["failed"] == 1

    def test_optional_failure_does_not_block(self) -> None:
        from tools.scripts.local_ci_mirror import GateResult

        summary = summarize([GateResult("hb", STATUS_FAILED, optional=True)])
        assert summary["ok"] is True
        assert summary["failed"] == 0

    def test_strict_skips_block(self) -> None:
        from tools.scripts.local_ci_mirror import GateResult

        summary = summarize([GateResult("s", STATUS_SKIPPED)], strict_skips=True)
        assert summary["ok"] is False
        assert summary["skipped"] == 1


class TestMain:
    def test_list_mode_prints_gates(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--list"]) == 0
        out = capsys.readouterr().out
        for name in ("lint", "quality-gate", "secret-scan"):
            assert name in out

    def test_unknown_gate_exits_two(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--only", "no-such-gate"]) == 2
        assert "未知门禁" in capsys.readouterr().err

    def test_json_output_shape(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--only", "ci-heartbeat", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "results" in payload and "summary" in payload
        assert payload["results"][0]["name"] == "ci-heartbeat"
        assert payload["summary"]["total"] == 1

    def test_empty_registry_selection_runs_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--only", "lint", "--skip", "lint", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["total"] == 0


class TestRegistryDataclass:
    def test_registry_default_is_empty(self) -> None:
        assert GateRegistry().names() == []
