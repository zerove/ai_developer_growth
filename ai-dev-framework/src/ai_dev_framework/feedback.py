"""
ADG Feedback — 误报回馈 + 规则自动学习

## 提取说明

本包以 ``pip install ai-dev-framework`` 分发, 会被复制进任意下游项目, 因此
**不能** eager import 主仓的 ``tools.scripts.rules_engine.feedback`` —— 那会让
本包无法独立安装 (与 redos.py 同一提取策略): 以下常量/类型/函数由主仓
``feedback.py`` **原样提取**, 非重写; 两处不一致时以主仓为准。
行为对齐由 tests/test_feedback_parity.py 锁定。

在提取的核心之上, 本包额外提供自动更新规则配置 (exclude_files) 的能力。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

# ── 以下原样提取自 tools/scripts/rules_engine/feedback.py ─────────────

# 存储路径: ~/.cache/adg/feedback.json
CACHE_DIR = Path.home() / ".cache" / "adg"
FEEDBACK_FILE = CACHE_DIR / "feedback.json"

# 当误报率 >= 此阈值时，规则自动降一级
AUTO_DOWNGRADE_THRESHOLD = 0.6  # 60% 的报告是误报

# 最少报告次数才触发自动降级
MIN_REPORTS_FOR_DOWNGRADE = 5


class RuleFeedback(TypedDict):
    total_reports: int
    false_positives: int
    files: list[dict[str, Any]]
    downgraded: bool


class RuleFeedbackRecord(RuleFeedback, total=False):
    """主仓 4 键 + 包内扩展键 auto_excluded (auto_update_config 运行时追加)。

    仅类型层差异, 不改变 _load_feedback/_save_feedback 的运行时行为。
    """

    auto_excluded: list[str]


class FeedbackData(TypedDict):
    rules: dict[str, RuleFeedbackRecord]
    total_feedback: int


class FeedbackStats(TypedDict):
    total_feedback: int
    tracked_rules: int
    downgraded_rules: int


def _load_feedback() -> FeedbackData:
    """加载反馈数据。"""
    if FEEDBACK_FILE.exists():
        try:
            raw: dict[str, Any] = json.loads(FEEDBACK_FILE.read_text())
            return {
                "rules": {
                    k: {
                        "total_reports": v.get("total_reports", 0),
                        "false_positives": v.get("false_positives", 0),
                        "files": v.get("files", []),
                        "downgraded": v.get("downgraded", False),
                    }
                    for k, v in raw.get("rules", {}).items()
                },
                "total_feedback": raw.get("total_feedback", 0),
            }
        except (json.JSONDecodeError, OSError):
            pass
    return {"rules": {}, "total_feedback": 0}


def _save_feedback(data: FeedbackData) -> None:
    """保存反馈数据。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(data, indent=2))


def get_feedback_stats() -> FeedbackStats:
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


# ── 增强: 自动更新规则配置 ──────────────────────

_RULES_HOME = Path.home() / ".config" / "adg" / "rules"


def auto_update_config(rule_id: str, filepath: str) -> bool:
    """根据误报反馈自动更新规则配置。

    如果某文件对同一规则的误报报告超过阈值，
    自动将该文件加入规则的 exclude_files。

    Returns:
        True if config was updated
    """
    data = _load_feedback()
    r = data.get("rules", {}).get(rule_id)
    if not r:
        return False

    # 检查同一文件的误报次数
    file_reports = [f for f in r.get("files", []) if f.get("file") == filepath]
    if len(file_reports) < 3:  # 最少 3 次才自动排除
        return False

    # 在规则配置中找到该规则并添加 exclude_files
    for yml_path in _RULES_HOME.rglob("anti_patterns.yml"):
        content = yml_path.read_text("utf-8")
        if rule_id in content:
            # 检查是否已排除
            fname = Path(filepath).name
            if fname in content:
                return False  # 已排除

            # 在规则的 id 行后添加 exclude_files
            import re

            updated = re.sub(
                rf"(- id: {re.escape(rule_id)}\n.*?)(?=\n- id:|\Z)",
                lambda m: m.group(1) + f"\n  exclude_files:\n  - '{fname}'",
                content,
                flags=re.DOTALL,
            )

            if updated != content:
                yml_path.write_text(updated, "utf-8")
                # 记录已自动排除
                if "auto_excluded" not in r:
                    r["auto_excluded"] = []
                if fname not in r["auto_excluded"]:
                    r["auto_excluded"].append(fname)
                _save_feedback(data)
                return True

    return False


# ── CLI 输出 ──────────────────────────────────


def print_feedback_stats(verbose: bool = False) -> int:
    """打印反馈统计。返回 exit code。"""
    stats = get_feedback_stats()
    data = _load_feedback()
    rules = data.get("rules", {})

    print("\n📊 ADG 反馈统计")
    print(f"{'=' * 50}")
    print(f"  总反馈数:    {stats['total_feedback']}")
    print(f"  追踪规则数:  {stats['tracked_rules']}")
    print(f"  已降级规则:  {stats['downgraded_rules']}")
    print()

    if verbose and rules:
        for rule_id, r in sorted(rules.items()):
            fp_rate = r["false_positives"] / r["total_reports"] * 100 if r["total_reports"] > 0 else 0
            status = "⬇️  已降级" if r.get("downgraded") else "✅"
            excluded = r.get("auto_excluded", [])
            excl_str = f", 自动排除: {len(excluded)} 文件" if excluded else ""
            print(f"  {status} {rule_id}")
            print(f"     总报告: {r['total_reports']}, 误报: {r['false_positives']} ({fp_rate:.0f}%){excl_str}")

    print()
    return 0
