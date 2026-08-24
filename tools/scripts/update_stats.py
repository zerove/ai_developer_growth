"""项目统计单一事实来源 (Single Source of Truth)。

从真实数据源自动采集 4 个关键指标，同步到 README.md 统计表，
并写入 .quality-trends/stats_history.jsonl 形成趋势记录。

数据源 (全部实测，非硬编码):
- 测试用例数: pytest --collect-only
- 实践案例数: case-studies/*.md 文件计数
- 架构决策数: docs/adr/*.md 文件计数
- 核心文档数: docs/**/*.md 文件计数

用法:
    python tools/scripts/update_stats.py            # 同步 README 并记录趋势
    python tools/scripts/update_stats.py --check    # 仅检查不一致 (CI 模式, 有漂移时退出码 1)
    python tools/scripts/update_stats.py --json     # JSON 输出统计结果
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.scripts._common import get_project_root

# 统计键 -> README 统计表行标签。
# 行匹配规则: 表格行中包含该标签文本。
README_STATS_TABLE: dict[str, str] = {
    "core_docs": "📄 核心文档",
    "cases": "📚 实践案例",
    "adrs": "📋 架构决策",
    "tests": "🧪 测试用例",
}


def count_docs(root: Path) -> int:
    """docs/ 下全部 Markdown 文档数。"""
    return len(list((root / "docs").rglob("*.md")))


def count_cases(root: Path) -> int:
    """case-studies/ 下案例文档数。"""
    return len(list((root / "case-studies").glob("*.md")))


def count_adrs(root: Path) -> int:
    """docs/adr/ 下架构决策记录数。"""
    adr_dir = root / "docs" / "adr"
    if not adr_dir.exists():
        return 0
    return len([p for p in adr_dir.glob("*.md") if p.name != "index.md" and not p.name.startswith("template")])


def count_tests(root: Path) -> int:
    """pytest 收集的测试用例数 (权威口径)。"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    if match:
        return int(match.group(1))
    raise RuntimeError(f"无法从 pytest 输出解析测试数: {result.stdout[-200:]}")


def collect_all(root: Path) -> dict[str, int]:
    """采集全部统计指标。"""
    return {
        "core_docs": count_docs(root),
        "cases": count_cases(root),
        "adrs": count_adrs(root),
        "tests": count_tests(root),
    }


def _read_readme_stats(readme: Path) -> dict[str, int | None]:
    """读取 README 统计表当前值; 缺失为 None。"""
    if not readme.exists():
        return {}
    content = readme.read_text(encoding="utf-8")
    current: dict[str, int | None] = {}
    for label in README_STATS_TABLE.values():
        match = re.search(rf"{re.escape(label)}\s*\|\s*(\d+)", content)
        current[label] = int(match.group(1)) if match else None
    return current


def sync_readme(readme: Path, stats: dict[str, int]) -> list[tuple[str, int | None, int]]:
    """将统计数据写回 README 统计表; 返回 (标签, 旧值, 新值) 变更列表。"""
    content = readme.read_text(encoding="utf-8")
    changes: list[tuple[str, int | None, int]] = []

    for key, label in README_STATS_TABLE.items():
        new_value = stats[key]
        pattern = rf"({re.escape(label)}\s*\|\s*)(\d+)"
        match = re.search(pattern, content)
        if match:
            old_value = int(match.group(2))
            if old_value != new_value:
                content = re.sub(pattern, rf"\g<1>{new_value}", content)
                changes.append((label, old_value, new_value))
        else:
            changes.append((label, None, new_value))

    readme.write_text(content, encoding="utf-8")
    return changes


def append_history(history_file: Path, stats: dict[str, int]) -> None:
    """追加一条统计快照到趋势历史文件。"""
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **stats}
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="项目统计单一事实来源同步")
    parser.add_argument("--check", action="store_true", help="仅检查不一致, 有漂移时退出码 1 (CI 模式)")
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON 输出统计结果")
    args = parser.parse_args()

    root = get_project_root()
    stats = collect_all(root)

    if args.as_json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    readme = root / "README.md"
    current = _read_readme_stats(readme)

    drift: list[str] = []
    for key, label in README_STATS_TABLE.items():
        documented = current.get(label)
        actual = stats[key]
        if documented != actual:
            drift.append(f"{label}: 文档 {documented} vs 实际 {actual}")

    if args.check:
        if drift:
            print("❌ README 统计与实际不一致:")
            for d in drift:
                print(f"   - {d}")
            print("修复: 本地运行 python tools/scripts/update_stats.py 后提交")
            return 1
        print("✅ README 统计与实际一致")
        return 0

    changes = sync_readme(readme, stats)
    if changes:
        print("🔄 README 统计已更新:")
        for label, old, new in changes:
            print(f"   - {label}: {old} -> {new}")
    else:
        print("✅ README 统计已是最新")

    append_history(root / ".quality-trends" / "stats_history.jsonl", stats)
    print(f"📈 趋势快照已记录: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
