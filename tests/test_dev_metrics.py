"""dev_metrics 单元测试（P2-1）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.scripts.dev_metrics import CONVENTIONAL, compute  # noqa: E402


class TestConventionalRegex:
    @pytest.mark.parametrize(
        "subject",
        ["feat(search): 新功能", "fix: 修复", "docs(tools): 文档", "refactor(mcp): 重构", "test: 测试"],
    )
    def test_valid(self, subject: str) -> None:
        assert CONVENTIONAL.match(subject)

    @pytest.mark.parametrize("subject", ["更新代码", "WIP stuff", "feat 缺冒号", "unknown(foo): bar!"])
    def test_invalid(self, subject: str) -> None:
        assert not CONVENTIONAL.match(subject)


class TestCompute:
    def test_counts(self) -> None:
        subjects = [
            "feat(a): x",
            "fix(b): y",
            "修复 ruff format 问题",
            "mypy 类型收窄",
            "随便写的",
        ]
        m = compute(subjects)
        assert m["total_commits"] == 5
        assert m["conventional_count"] == 2
        assert m["hook_fix_commits"] == 2

    def test_empty(self) -> None:
        m = compute([])
        assert m["total_commits"] == 0
        assert m["conventional_rate"] == 0.0
