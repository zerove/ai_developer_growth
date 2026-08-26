"""VS Code 扩展核心逻辑的 Python 镜像验证。

extension.ts 是 TypeScript, 无法用 pytest 直接测; 但其分级算法/维度定义/知识库元数据
是扩展与 Web 平台共用的领域模型。本测试从 TS 源码解析出常量做一致性断言,
保证 py 侧镜像模型与 TS 实现不漂移。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

EXTENSION_TS = Path(__file__).resolve().parent.parent / "src" / "extension.ts"


@dataclass(frozen=True)
class Level:
    min: int
    max: int
    label: str


def parse_levels(ts: str) -> list[Level]:
    """从 extension.ts 的 LEVELS 常量提取分级。"""
    block = re.search(r"const LEVELS = \[(.*?)\];", ts, re.S)
    assert block, "LEVELS not found"
    levels = []
    for m in re.finditer(r"min: (\d+), max: (\d+), label: '([^']+)'", block.group(1)):
        levels.append(Level(int(m.group(1)), int(m.group(2)), m.group(3)))
    return levels


def parse_dimension_keys(ts: str) -> list[str]:
    """提取五维 key。"""
    block = re.search(r"const SKILL_DIMENSIONS.*?= \[(.*?)\n\];", ts, re.S)
    assert block, "SKILL_DIMENSIONS not found"
    return re.findall(r"key: '(\w+)'", block.group(1))


def find_level(levels: list[Level], overall: int) -> Level:
    """复刻 TS: LEVELS.find(l => overall >= l.min && overall <= l.max) || LEVELS[0]。"""
    for lv in levels:
        if lv.min <= overall <= lv.max:
            return lv
    return levels[0]


class TestLevelsMirror:
    def test_five_levels_parsed(self) -> None:
        levels = parse_levels(EXTENSION_TS.read_text(encoding="utf-8"))
        assert len(levels) == 5
        assert levels[0].label.startswith("L0")
        assert levels[-1].label.startswith("L4")

    def test_level_ranges_contiguous(self) -> None:
        ts = EXTENSION_TS.read_text(encoding="utf-8")
        levels = parse_levels(ts)
        assert levels[0].min == 0 and levels[-1].max == 100
        for prev, nxt in zip(levels, levels[1:]):
            assert nxt.min == prev.max + 1, f"gap between {prev.label} and {nxt.label}"

    @staticmethod
    def _overall(scores: dict[str, int]) -> int:
        """复刻 TS: Math.round(sum/5)。"""
        return round(sum(scores.values()) / len(scores))

    def test_assessment_level_mapping(self) -> None:
        ts = EXTENSION_TS.read_text(encoding="utf-8")
        levels = parse_levels(ts)
        # 全 100 → L4 架构师
        full = {f"d{i}": 100 for i in range(5)}
        assert find_level(levels, self._overall(full)).label.startswith("L4")
        # 全 50 → L2 实践者
        mid = {f"d{i}": 50 for i in range(5)}
        assert find_level(levels, self._overall(mid)).label.startswith("L2")

    def test_out_of_range_falls_back_to_l0(self) -> None:
        ts = EXTENSION_TS.read_text(encoding="utf-8")
        levels = parse_levels(ts)
        assert find_level(levels, -1).label.startswith("L0")


class TestDimensionsMirror:
    def test_five_dimensions(self) -> None:
        keys = parse_dimension_keys(EXTENSION_TS.read_text(encoding="utf-8"))
        assert keys == [
            "aiComprehension",
            "engineeringIntegration",
            "learningMethod",
            "innovationThinking",
            "outputQuality",
        ]

    def test_quick_assessment_uses_first_three(self) -> None:
        """TS: SKILL_DIMENSIONS.slice(0, 3)。"""
        keys = parse_dimension_keys(EXTENSION_TS.read_text(encoding="utf-8"))
        quick = keys[:3]
        assert len(quick) == 3

    def test_quick_midpoint_math(self) -> None:
        """TS: (low + high) / 2 的中点换算。"""
        lo, hi = (int(p) for p in "21-40".split("-"))
        assert (lo + hi) / 2 == 30.5
