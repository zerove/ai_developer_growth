"""基线双 schema 隔离回归测试。

.jcode/baseline.json (schema B, 棘轮 int 计数) 与 quality-gate 基线
(schema A, files 值为 dict 详情) 曾共用默认路径, 交叉读取会 TypeError。
此文件证明两个方向都: 不崩溃、不产生虚假结果。
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts.config.models import BaselineConfig
from tools.scripts.hooks.domain_checks import (
    _apply_baseline_ratchet,
    _load_issue_baseline,
)
from tools.scripts.quality_gate import BaselineManager
from tools.scripts.rules_engine.models import CheckResult, Issue


def test_schema_a_file_is_treated_as_empty_by_ratchet_loader(tmp_path: Path) -> None:
    """schema A (files 值为 dict) 喂给棘轮加载器: 不崩溃, 视为空基线。"""
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "version": 1,
                "files": {
                    "a.py": {
                        "R1:1:0": {
                            "rule_id": "R1",
                            "line": 1,
                            "column": 0,
                            "severity": "warning",
                            "message": "msg",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = _load_issue_baseline(baseline)
    # 不崩溃, 且 dict 值全部被跳过 → 无任何计数
    assert loaded is not None
    assert all(counts == {} for counts in loaded.values())
    # 棘轮入口 (domain_checks.py:359) 同样不崩溃, 且零豁免
    results = [
        (
            Path("a.py"),
            {
                "passed": False,
                "issues": [{"type": "structure", "message": "函数超过 10 行 (实际 20 行)"}],
            },
        )
    ]
    filtered, exempt, _note = _apply_baseline_ratchet(results, baseline)
    assert exempt == 0
    assert filtered[0][1]["issues"]  # 问题全部保留, 无虚假豁免


def test_schema_b_file_yields_no_spurious_deltas_in_compare(tmp_path: Path) -> None:
    """schema B (files 值为 int 计数) 喂给 compare_with_baseline:
    不崩溃, 不产生任何虚假 delta。"""
    baseline_file = tmp_path / "quality-gate-baseline.json"
    baseline_file.write_text(
        json.dumps(
            {
                "version": 1,
                # 两个 key 分别命中两处守卫: "R1:1:0" 与当前 rule_key 巧合相等
                # (→ _classify_severity_change 守卫), 另一个走 fixed 路径守卫。
                "files": {"a.py": {"R1:1:0": 3, "structure:函数超过 10 行": 1}},
            }
        ),
        encoding="utf-8",
    )
    manager = BaselineManager(BaselineConfig(path=str(baseline_file)))
    current = [
        CheckResult(
            file="a.py",
            issues=[
                Issue(
                    rule_id="R1",
                    severity="warning",
                    category="style",
                    file="a.py",
                    line=1,
                    message="msg",
                )
            ],
        )
    ]
    comparison = manager.compare_with_baseline(current)
    # int 值被守卫跳过: 既不虚构 fixed/worsened/improved, 也不误判 new
    assert comparison["new"] == []
    assert comparison["fixed"] == []
    assert comparison["worsened"] == []
    assert comparison["improved"] == []
    assert comparison["summary"]["new_count"] == 0
    assert comparison["summary"]["fixed_count"] == 0
    assert comparison["summary"]["worsened_count"] == 0
    assert comparison["summary"]["improved_count"] == 0
