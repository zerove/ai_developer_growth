"""变异测试得分统计: 从 mutmut 缓存库算击杀率, 按阈值判定。

mutmut 2.x 把每个变异体的状态写进 SQLite 缓存 (`.mutmut-cache`), 但
`mutmut results` 只列出存活变异体, 不给击杀数 —— 没法据此设阈值门禁。
本脚本直接读缓存库统计各类状态, 供夜间作业判定"变异测试是否还有判别力":
击杀率低于阈值即失败, 避免"跑完就算过"的假绿。
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

STATUS_KILLED = "ok_killed"
STATUS_SURVIVED = "bad_survived"
STATUS_TIMEOUT = "bad_timeout"
STATUS_SUSPICIOUS = "ok_suspicious"
STATUS_SKIPPED = "skipped"

#: 计入"已测试变异体"的状态 (未测试/跳过的不算)
TESTED_STATUSES = (STATUS_KILLED, STATUS_SURVIVED, STATUS_TIMEOUT)


def read_status_counts(cache_path: Path) -> dict[str, int]:
    """读取 mutmut 缓存库里的变异体状态计数。

    Args:
        cache_path: mutmut 缓存库路径

    Returns:
        状态 → 数量; 缓存不存在或结构不符时返回空字典
    """
    if not cache_path.exists():
        return {}
    connection = sqlite3.connect(str(cache_path))  # 连接在 finally 中释放
    try:
        rows = connection.execute("SELECT status, COUNT(*) FROM Mutant GROUP BY status").fetchall()
    except sqlite3.Error:
        return {}
    finally:
        connection.close()
    return {str(status): int(count) for status, count in rows}


def kill_rate(counts: dict[str, int]) -> float:
    """计算击杀率 (击杀数 / 已测试变异体数)。

    Args:
        counts: 状态计数

    Returns:
        0.0 ~ 1.0 的击杀率; 没有已测试变异体时返回 0.0
    """
    tested = sum(counts.get(status, 0) for status in TESTED_STATUSES)
    if tested == 0:
        return 0.0
    return counts.get(STATUS_KILLED, 0) / tested


def format_summary(counts: dict[str, int], rate: float) -> str:
    """把统计结果格式化成报告文本。

    Args:
        counts: 状态计数
        rate: 击杀率

    Returns:
        多行文本
    """
    killed = counts.get(STATUS_KILLED, 0)
    survived = counts.get(STATUS_SURVIVED, 0)
    timed_out = counts.get(STATUS_TIMEOUT, 0)
    suspicious = counts.get(STATUS_SUSPICIOUS, 0)
    skipped = counts.get(STATUS_SKIPPED, 0)
    return "\n".join(
        [
            "",
            "=== 变异测试得分 ===",
            f"击杀 (ok_killed):        {killed}",
            f"存活 (bad_survived):     {survived}",
            f"超时 (bad_timeout):      {timed_out}",
            f"可疑 (ok_suspicious):    {suspicious}",
            f"跳过 (skipped):          {skipped}",
            f"击杀率: {rate:.1%}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    """命令行入口: 统计击杀率并按阈值判定。

    Args:
        argv: 命令行参数 (默认取 sys.argv)

    Returns:
        0 表示达到阈值; 1 表示低于阈值或缓存缺失
    """
    parser = argparse.ArgumentParser(description="统计 mutmut 变异击杀率并按阈值判定")
    parser.add_argument("--cache", type=Path, default=Path(".mutmut-cache"), help="mutmut 缓存库路径")
    parser.add_argument("--min-rate", type=float, default=0.6, help="最低击杀率 (0~1)")
    parser.add_argument("--report", type=Path, help="把统计结果追加到这个报告文件")
    args = parser.parse_args(argv)

    counts = read_status_counts(args.cache)
    rate = kill_rate(counts)
    summary = format_summary(counts, rate)
    print(summary)

    if args.report:
        args.report.write_text(
            args.report.read_text(encoding="utf-8") + summary + "\n",
            encoding="utf-8",
        )

    if not counts:
        print("❌ 未找到 mutmut 缓存库: 变异测试没有真正执行")
        return 1
    if rate < args.min_rate:
        print(f"❌ 变异击杀率 {rate:.1%} 低于阈值 {args.min_rate:.1%}")
        return 1
    print(f"✅ 变异击杀率 {rate:.1%} 达到阈值 {args.min_rate:.1%}")
    return 0


if __name__ == "__main__":  # pragma: no cover - 脚本入口
    raise SystemExit(main())
