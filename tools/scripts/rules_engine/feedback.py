"""误报回馈机制 — 记录用户标记的误报并自动降低规则优先级。

用户在检查结果中标记某个问题为误报后，系统会记录该规则在该文件
上下文中的误报次数，当同一规则的误报率超过阈值时自动降低其严重度。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

# 存储路径: ~/.cache/adg/feedback.json
CACHE_DIR = Path.home() / ".cache" / "adg"
FEEDBACK_FILE = CACHE_DIR / "feedback.json"

# 当误报率 >= 此阈值时，规则自动降一级
AUTO_DOWNGRADE_THRESHOLD = 0.6  # 60% 的报告是误报

# 最少报告次数才触发自动降级
MIN_REPORTS_FOR_DOWNGRADE = 5


def _load_feedback() -> dict:
    """加载反馈数据。"""
    if FEEDBACK_FILE.exists():
        try:
            return json.loads(FEEDBACK_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"rules": {}, "total_feedback": 0}


def _save_feedback(data: dict) -> None:
    """保存反馈数据。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(data, indent=2))


def mark_false_positive(rule_id: str, filepath: str, severity: str) -> dict:
    """标记一个问题为误报。

    Args:
        rule_id: 规则ID (如 'py-hardcoded-secret')
        filepath: 文件路径
        severity: 原始严重度

    Returns:
        反馈记录。
    """
    data = _load_feedback()
    data["total_feedback"] = data.get("total_feedback", 0) + 1

    # 按规则统计
    if rule_id not in data["rules"]:
        data["rules"][rule_id] = {
            "total_reports": 0,
            "false_positives": 0,
            "files": [],
            "downgraded": False,
        }
    r = data["rules"][rule_id]
    r["total_reports"] += 1
    r["false_positives"] += 1
    r["files"].append({"file": filepath, "severity": severity, "timestamp": time.time()})
    r["files"] = r["files"][-50:]  # 只保留最近 50 条

    _save_feedback(data)

    return {
        "rule_id": rule_id,
        "total_reports": r["total_reports"],
        "false_positives": r["false_positives"],
        "should_downgrade": _should_downgrade(rule_id, data),
    }


def get_effective_severity(rule_id: str, original_severity: str) -> str:
    """获取考虑误报率后的有效严重度。

    如果规则误报率过高，自动降一级。
    """
    if _should_downgrade(rule_id, _load_feedback()):
        downgrade_map = {"error": "warning", "warning": "info", "info": "info"}
        return downgrade_map.get(original_severity, original_severity)
    return original_severity


def _should_downgrade(rule_id: str, data: dict) -> bool:
    """判断规则是否应该降级。"""
    r = data.get("rules", {}).get(rule_id)
    if not r:
        return False
    if r["total_reports"] < MIN_REPORTS_FOR_DOWNGRADE:
        return False
    fp_rate = r["false_positives"] / r["total_reports"]
    return fp_rate >= AUTO_DOWNGRADE_THRESHOLD


def get_feedback_stats() -> dict:
    """获取反馈统计数据。"""
    data = _load_feedback()
    rules = data.get("rules", {})
    downgraded = sum(1 for r in rules.values() if r.get("downgraded"))
    return {
        "total_feedback": data.get("total_feedback", 0),
        "tracked_rules": len(rules),
        "downgraded_rules": downgraded,
    }


def reset_feedback() -> None:
    """重置所有反馈数据。"""
    _save_feedback({"rules": {}, "total_feedback": 0})
