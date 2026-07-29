"""
ADG Feedback — 误报回馈 + 规则自动学习

包装 tools/scripts/rules_engine/feedback.py 的核心逻辑，
加入自动更新规则配置（exclude_files）的能力。
"""

from __future__ import annotations

import sys
from pathlib import Path

# Re-export from existing implementation
from tools.scripts.rules_engine.feedback import (
    AUTO_DOWNGRADE_THRESHOLD,
    CACHE_DIR,
    FEEDBACK_FILE,
    MIN_REPORTS_FOR_DOWNGRADE,
    FeedbackData,
    FeedbackStats,
    FalsePositiveResult,
    get_feedback_stats,
    get_effective_severity,
    mark_false_positive,
    reset_feedback,
    _load_feedback,
    _save_feedback,
    _should_downgrade,
)

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

    print(f"\n📊 ADG 反馈统计")
    print(f"{'='*50}")
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
