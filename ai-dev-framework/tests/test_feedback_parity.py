"""包内内置 feedback 与主仓 feedback 的一致性 (parity) 测试。

提取策略要求 "两处不一致时以主仓为准" —— 本测试在主仓可达时逐项比对常量与
函数行为; 主仓不可达 (独立分发场景) 时跳过, 与 test_redos_gate.py 同一模式。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import ai_dev_framework.feedback as pkg  # noqa: E402

# 样例反馈文件: 含完整键 / 缺失键 / 附加键, 覆盖 _load_feedback 的归一化路径
_FIXTURE = {
    "rules": {
        "py-eval": {
            "total_reports": 6,
            "false_positives": 4,
            "files": [{"file": "a.py", "severity": "error", "timestamp": 1.0}],
            "downgraded": True,
        },
        "ts-legacy": {
            "total_reports": 2,
            "files": [],
        },
        "go-hardcoded": {
            "total_reports": 9,
            "false_positives": 9,
            "files": [],
            "downgraded": False,
            "auto_excluded": ["main.go"],
            "extra_unknown": 1,
        },
    },
    "total_feedback": 17,
}


def _load_parent() -> object:
    """主仓 feedback 模块; 不可达时跳过 (独立分发场景)。"""
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from tools.scripts.rules_engine import feedback as parent
    except ImportError:
        pytest.skip("主仓 feedback 不可达 (分发场景)")
    return parent


def _patch_both(monkeypatch: pytest.MonkeyPatch, parent: object, tmp_path: Path) -> tuple[Path, Path]:
    """把两份模块的存储路径都指到临时目录, 避免触碰真实用户缓存。"""
    pkg_dir, parent_dir = tmp_path / "pkg", tmp_path / "parent"
    monkeypatch.setattr(pkg, "CACHE_DIR", pkg_dir)
    monkeypatch.setattr(pkg, "FEEDBACK_FILE", pkg_dir / "feedback.json")
    monkeypatch.setattr(parent, "CACHE_DIR", parent_dir)
    monkeypatch.setattr(parent, "FEEDBACK_FILE", parent_dir / "feedback.json")
    return pkg_dir / "feedback.json", parent_dir / "feedback.json"


class TestFeedbackParity:
    def test_constants_parity(self) -> None:
        """常量逐项一致 —— 路径与阈值漂移会静默改变降级行为。"""
        parent = _load_parent()
        for name in ("CACHE_DIR", "FEEDBACK_FILE", "AUTO_DOWNGRADE_THRESHOLD", "MIN_REPORTS_FOR_DOWNGRADE"):
            assert getattr(pkg, name) == getattr(parent, name), f"常量漂移: {name}"

    def test_load_feedback_parity(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        parent = _load_parent()
        pkg_file, parent_file = _patch_both(monkeypatch, parent, tmp_path)

        # 1) 文件不存在: 两边都应返回同一默认值
        assert pkg._load_feedback() == parent._load_feedback()

        # 2) 非法 JSON: 两边都应退回默认值
        pkg_file.parent.mkdir(parents=True, exist_ok=True)
        pkg_file.write_text("{not json", encoding="utf-8")
        parent_file.parent.mkdir(parents=True, exist_ok=True)
        parent_file.write_text("{not json", encoding="utf-8")
        assert pkg._load_feedback() == parent._load_feedback()

        # 3) 归一化行为: 缺失键补默认、附加键被丢弃
        pkg_file.write_text(json.dumps(_FIXTURE), encoding="utf-8")
        parent_file.write_text(json.dumps(_FIXTURE), encoding="utf-8")
        got_pkg, got_parent = pkg._load_feedback(), parent._load_feedback()
        assert got_pkg == got_parent, "归一化行为与主仓分歧"

    def test_save_roundtrip_parity(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        parent = _load_parent()
        pkg_file, parent_file = _patch_both(monkeypatch, parent, tmp_path)

        pkg._save_feedback(dict(_FIXTURE))
        parent._save_feedback(dict(_FIXTURE))
        assert pkg_file.read_text(encoding="utf-8") == parent_file.read_text(encoding="utf-8"), "落盘格式分歧"

    def test_stats_and_reset_parity(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        parent = _load_parent()
        pkg_file, parent_file = _patch_both(monkeypatch, parent, tmp_path)

        pkg_file.parent.mkdir(parents=True, exist_ok=True)
        pkg_file.write_text(json.dumps(_FIXTURE), encoding="utf-8")
        parent_file.parent.mkdir(parents=True, exist_ok=True)
        parent_file.write_text(json.dumps(_FIXTURE), encoding="utf-8")

        assert pkg.get_feedback_stats() == parent.get_feedback_stats()

        pkg.reset_feedback()
        parent.reset_feedback()
        assert pkg_file.read_text(encoding="utf-8") == parent_file.read_text(encoding="utf-8")
        empty = {"total_feedback": 0, "tracked_rules": 0, "downgraded_rules": 0}
        assert pkg.get_feedback_stats() == parent.get_feedback_stats() == empty
