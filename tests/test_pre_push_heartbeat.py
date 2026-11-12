"""pre-push 门禁接入 CI 心跳探测（ADR-057 落地意图的补齐）。

契约：
- 受跟踪的 hook 源 `.jcode/hooks/pre-push` 必须包含心跳探测步骤；
- 该步骤**不得**阻断推送（远端 CI 失效属外部条件，不能锁死开发者）；
- 未配置 token 时必须跳过（不产生噪音），且不得把 token 缺失当作失败。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SOURCE = REPO_ROOT / ".jcode" / "hooks" / "pre-push"


@pytest.fixture(scope="module")
def hook_text() -> str:
    """受跟踪的 pre-push hook 源。"""
    assert HOOK_SOURCE.is_file(), f"缺少受跟踪的 hook 源: {HOOK_SOURCE}"
    return HOOK_SOURCE.read_text(encoding="utf-8")


class TestPrePushHeartbeat:
    def test_hook_runs_ci_heartbeat(self, hook_text: str) -> None:
        """心跳探测必须在受跟踪的 hook 源里（否则其他克隆者会失去该能力）。"""
        assert "ci-heartbeat" in hook_text

    def test_heartbeat_step_does_not_block_push(self, hook_text: str) -> None:
        """心跳失败只告警：其所在分支不得把 fail 置 1。"""
        match = re.search(
            r"if ! \$PYTHON -m tools\.scripts\.hooks_runner ci-heartbeat; then(?P<body>.*?)\nfi",
            hook_text,
            re.DOTALL,
        )
        assert match is not None, "未找到心跳探测分支"
        body = match.group("body")
        assert "fail=1" not in body, "心跳探测不得阻断推送（远端 CI 失效属外部条件）"
        assert "⚠️" in body, "心跳失败必须显式告警，不能静默"

    def test_missing_token_skips_probe(self, hook_text: str) -> None:
        """未配置 token 时跳过探测，不报错。"""
        assert "GITHUB_TOKEN:-" in hook_text
        assert "GH_TOKEN:-" in hook_text
        assert "跳过远端 CI 心跳探测" in hook_text

    def test_step_numbering_is_consistent(self, hook_text: str) -> None:
        """三个步骤的编号必须一致（[1/3] [2/3] [3/3]）。"""
        for index in (1, 2, 3):
            assert f"[{index}/3]" in hook_text, f"缺少步骤编号 [{index}/3]"

    def test_core_gates_still_present(self, hook_text: str) -> None:
        """接入心跳不得挤掉既有核心门禁。"""
        for command in (
            "hooks.pre_push",
            "hooks_runner lint",
            "hooks_runner typecheck",
            "hooks_runner test",
            "hooks_runner quality-gate --full",
            "hooks_runner baseline recompute",
        ):
            assert command in hook_text, f"核心门禁缺失: {command}"
