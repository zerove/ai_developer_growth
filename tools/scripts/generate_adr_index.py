#!/usr/bin/env python3
"""从 docs/adr/ADR-*.md 自动生成 docs/adr/ADR.md 的索引表。

背景 (Phase 38):
    ADR 索引长期手工维护, 结果磁盘上 53 个 ADR 只登记了 20 个, 而索引
    自称"汇总所有架构决策记录"。缺口不是一次疏漏 —— 手工表必然持续漂移。

本脚本把索引表变成**生成物**: 扫描全部 ADR 文件, 抽取 ID / 标题 / 状态 /
日期, 按 ID 倒序重排, 替换 ADR.md 中标记区间的表格。

用法:
    python tools/scripts/generate_adr_index.py            # 写入 (默认)
    python tools/scripts/generate_adr_index.py --check    # 只校验, 有差异退出 1
    python tools/scripts/generate_adr_index.py --dry-run  # 打印将写入的内容

退出码: 0 一致 / 1 --check 下发现差异 / 2 读取失败
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ADR_DIR = REPO_ROOT / "docs" / "adr"
INDEX_PATH = ADR_DIR / "ADR.md"

# 索引表在 ADR.md 中的边界标记
BEGIN_MARKER = "<!-- BEGIN GENERATED ADR INDEX -->"
END_MARKER = "<!-- END GENERATED ADR INDEX -->"

# ADR 文件名形如 ADR-062-slug.md; 001 有两个变体 (001 / 001b), 允许后缀
FILENAME_RE = re.compile(r"^ADR-(\d{3})(?P<suffix>[a-z]?)-.+\.md$", re.IGNORECASE)

# 状态与日期的取值可能带修饰, 如 "接受 (规划,未实施)" / "**Accepted** (2026-08-29)"
# 区块末尾不要求一定有下一个 '##' —— 部分 ADR 把 '## 状态' 放在文末。
STATUS_RE = re.compile(r"^##+\s*状态\s*$(.*?)(?=^##|\Z)", re.MULTILINE | re.DOTALL)
DATE_RE = re.compile(r"^##+\s*日期\s*$(.*?)(?=^##|\Z)", re.MULTILINE | re.DOTALL)
# 标题的冒号前可能夹着修饰, 如 "# ADR-013 (修订): 覆盖率报告..."。
# 必须允许 ')' 与空白, 否则会漏掉这类文件。
TITLE_RE = re.compile(r"^#\s*(ADR-\d{3}[a-z]?)\s*(?:\([^)]*\))?\s*[:：]\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class Entry:
    """一条 ADR 记录。"""

    number: int
    suffix: str
    slug: str
    title: str
    status: str
    date: str

    @property
    def filename(self) -> str:
        suffix = f"-{self.suffix}" if self.suffix else ""
        return f"ADR-{self.number:03d}{suffix}-{self.slug}.md"

    @property
    def wiki_link(self) -> str:
        """Obsidian wikilink, 竖线需转义。

        wikilink 语法为 [[目标|显示名]], 目标里再出现裸竖线会被截断,
        因此文件名中的 '|' 必须写成 '\\|' (此前只写在 docstring 里,
        实现漏了转义, 属于潜伏缺陷)。
        """
        target = self.filename[:-3].replace("|", "\\|")
        return f"[[{target}|ADR-{self.number:03d}{self.suffix}]]"


def _clean_block(match: re.Match[str] | None) -> str:
    """从 '## 状态' / '## 日期' 区块里抽出第一段非空文本。"""
    if match is None:
        return ""
    body = match.group(1)
    for line in body.splitlines():
        line = line.strip().strip("*").strip()
        if line:
            return line
    return ""


def _status_badge(status: str) -> str:
    """把原始状态文字归一为索引里的徽标。

    索引历史上有两种写法 ("✅ 已接受" / "✅ 已通过"), 为保持表格可读,
    这里按关键词归一, 未知取值原样透出以免掩盖信息。
    """
    raw = status.replace("**", "")
    if not raw:
        # 确实没有 '## 状态' 区块的 ADR (如 ADR-017)。用 '—' 如实表示
        # "无此字段", 而不是编造一个状态。
        return "—"
    # '修订' 优先于 '接受': ADR-013 写的是 "**Revised** (2026-08-29)",
    # 但正文里也含"接受"字样, 先判修订才不会误标。
    if "修订" in raw or "revised" in raw.lower():
        return "✏️ 已修订"
    if "接受" in raw or "accept" in raw.lower():
        return "✅ 已接受"
    if "废弃" in raw or "拒绝" in raw or "reject" in raw.lower():
        return "❌ 已废弃"
    if "替代" in raw or "superseded" in raw.lower():
        return "🔄 已替代"
    return raw


def parse_adr(path: Path) -> Entry | None:
    """从单个 ADR 文件抽取元数据。非 ADR 文件或格式异常时返回 None。"""
    name_match = FILENAME_RE.match(path.name)
    if name_match is None:
        return None

    text = path.read_text(encoding="utf-8")

    title_match = TITLE_RE.search(text)
    if title_match is None:
        print(f"⚠️  {path.name}: 缺少 '# ADR-XXX: 标题' 一级标题, 已跳过", file=sys.stderr)
        return None

    number = int(name_match.group(1))
    suffix = name_match.group("suffix").lower()
    status = _status_badge(_clean_block(STATUS_RE.search(text)))
    date = _clean_block(DATE_RE.search(text))

    slug = path.stem.split("-", 2)[2] if path.stem.count("-") >= 2 else ""

    return Entry(
        number=number,
        suffix=suffix,
        slug=slug,
        title=title_match.group(2).strip(),
        status=status,
        date=date or "—",
    )


def collect_entries() -> list[Entry]:
    """扫描 ADR 目录, 返回按编号倒序排列的条目。"""
    entries = [e for e in (parse_adr(p) for p in sorted(ADR_DIR.glob("ADR-*.md"))) if e]
    # 编号倒序; 同编号时后缀字母升序 (001 在 001b 前)
    entries.sort(key=lambda e: (-e.number, e.suffix))
    return entries


def render_table(entries: list[Entry]) -> str:
    """生成索引表格文本。"""
    lines = [
        BEGIN_MARKER,
        "",
        "| ID | 标题 | 状态 | 日期 |",
        "|----|------|------|------|",
    ]
    for e in entries:
        lines.append(f"| {e.wiki_link} | {e.title} | {e.status} | {e.date} |")
    lines.extend(["", END_MARKER])
    return "\n".join(lines)


def splice_index(index_text: str, table: str) -> str:
    """把生成的表格写回 ADR.md 的标记区间。

    若标记不存在, 则退回到"表头下第一张表"的替换方式, 以兼容旧文件。
    """
    if BEGIN_MARKER in index_text and END_MARKER in index_text:
        head, _, rest = index_text.partition(BEGIN_MARKER)
        _, _, tail = rest.partition(END_MARKER)
        return f"{head}{table}{tail}"

    # 兼容路径: 替换 "| ID | 标题 | 状态 | 日期 |" 起始的那张表
    lines = index_text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("| ID | 标题 |"))
    except StopIteration:
        raise SystemExit("❌ ADR.md 中找不到索引表, 且缺少生成标记")

    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1

    new_lines = lines[:start] + table.splitlines() + lines[end:]
    return "\n".join(new_lines) + ("\n" if index_text.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="自动生成 ADR 索引表")
    parser.add_argument("--check", action="store_true", help="只校验, 不一致则退出 1")
    parser.add_argument("--dry-run", action="store_true", help="打印生成内容")
    args = parser.parse_args()

    if not INDEX_PATH.exists():
        print(f"❌ 索引文件不存在: {INDEX_PATH}", file=sys.stderr)
        return 2

    entries = collect_entries()
    if not entries:
        print("❌ 未解析到任何 ADR", file=sys.stderr)
        return 2

    table = render_table(entries)
    current = INDEX_PATH.read_text(encoding="utf-8")

    if args.dry_run:
        print(table)
        return 0

    updated = splice_index(current, table)

    if updated == current:
        print(f"✅ ADR 索引已是最新 ({len(entries)} 条)")
        return 0

    if args.check:
        print(
            f"❌ ADR 索引与 {len(entries)} 个 ADR 文件不一致, 请运行: python tools/scripts/generate_adr_index.py",
            file=sys.stderr,
        )
        return 1

    INDEX_PATH.write_text(updated, encoding="utf-8")
    print(f"✅ 已更新 ADR 索引: {len(entries)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
