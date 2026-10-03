"""Tests for tools/scripts/generate_adr_index.py (ADR 索引自动生成).

背景 (Phase 38):
    ADR 索引长期手工维护, 磁盘 53 个 ADR 只登记 20 个, 而索引自称
    "汇总所有架构决策记录"。手工表必然持续漂移, 所以改为生成物,
    并接一个 on_commit 的 `--check` 门禁防止再次腐化。

这些测试确保生成器本身可靠: 解析各种历史写法、幂等、能发现漂移。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import acquire_repo_mutation_lock as _acquire_repo_mutation_lock  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "scripts" / "generate_adr_index.py"
ADR_DIR = REPO_ROOT / "docs" / "adr"
INDEX_PATH = ADR_DIR / "ADR.md"


def _load_module() -> Any:
    """按路径加载生成器模块 (文件名含连字符, 不能直接 import)。

    必须先注册进 sys.modules: 模块里的 @dataclass 在求值时会回查
    sys.modules[cls.__module__], 未注册会抛 AttributeError。
    """
    spec = importlib.util.spec_from_file_location("generate_adr_index", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class StatusBadgeTest(unittest.TestCase):
    """状态文字归一 —— 各种历史写法都要有确定结果。"""

    @staticmethod
    def _badge(raw: str) -> str:
        return str(_load_module()._status_badge(raw))

    def test_accept_variants(self) -> None:
        self.assertEqual(self._badge("接受"), "✅ 已接受")
        self.assertEqual(self._badge("**Accepted** (2026-08-29)"), "✅ 已接受")

    def test_revised_wins_over_accept(self) -> None:
        """ADR-013 写的是 '**Revised**' 但正文含'接受', 不得误标为已接受。"""
        badge = self._badge("**Revised** (2026-08-29) — 原 ADR 误判根因")
        self.assertEqual(badge, "✏️ 已修订")

    def test_missing_status_is_dash(self) -> None:
        """没有状态字段时如实显示 '—', 不编造状态。"""
        self.assertEqual(self._badge(""), "—")

    def test_unknown_status_passes_through(self) -> None:
        """未知取值原样透出, 不静默归一成'已接受'。"""
        self.assertEqual(self._badge("待定"), "待定")


class ParseADRTest(unittest.TestCase):
    """单文件解析 —— 覆盖真实存在的历史格式变体。"""

    @staticmethod
    def _parse(name: str) -> Any:
        module = _load_module()
        return module.parse_adr(ADR_DIR / name)

    def test_parses_modern_adr(self) -> None:
        entry = self._parse("ADR-062-fail-open-detector-validates-executability.md")
        assert entry is not None
        self.assertEqual(entry.number, 62)
        self.assertEqual(entry.status, "✅ 已接受")
        self.assertEqual(entry.date, "2026-10-02")
        self.assertIn("可执行性", entry.title)

    def test_parses_title_with_parenthetical_modifier(self) -> None:
        """ADR-013 标题形如 '# ADR-013 (修订): ...', 不得被漏掉。"""
        entry = self._parse("ADR-013-pytest-xdist-coverage-known-issue.md")
        assert entry is not None
        self.assertEqual(entry.number, 13)
        self.assertEqual(entry.status, "✏️ 已修订")
        self.assertIn("假 0%", entry.title)

    def test_parses_adr_without_status_section(self) -> None:
        """ADR-017 确实没有 '## 状态', 应降级为 '—' 而非报错。"""
        entry = self._parse("ADR-017-py-log-print-downgrade.md")
        assert entry is not None
        self.assertEqual(entry.status, "—")
        self.assertEqual(entry.date, "—")

    def test_returns_none_for_non_adr_filename(self) -> None:
        module = _load_module()
        self.assertIsNone(module.parse_adr(ADR_DIR / "ADR.md"))


class IndexCompletenessTest(unittest.TestCase):
    """索引与磁盘文件的一致性 —— 这是本脚本存在的全部理由。"""

    def test_every_adr_file_is_indexed(self) -> None:
        module = _load_module()
        entries = module.collect_entries()
        on_disk = {p.name for p in ADR_DIR.glob("ADR-*.md")}

        # Entry.filename 是权威的属性 (带 ADR-NNN 前缀, 并在无字母后缀时省略 '-'),
        # 直接用它与磁盘文件名对账, 不在测试里重算拼接规则。
        indexed = {e.filename for e in entries}
        missing = on_disk - indexed
        self.assertEqual(
            missing,
            set(),
            f"这些 ADR 未被索引, 索引不再自称'汇总所有': {sorted(missing)}",
        )

    def test_no_duplicate_numbers(self) -> None:
        module = _load_module()
        entries = module.collect_entries()
        keys = [(e.number, e.suffix) for e in entries]
        self.assertEqual(len(keys), len(set(keys)), "索引中出现重复条目")

    def test_filename_roundtrips_to_disk(self) -> None:
        """Entry.filename 必须等于磁盘上的真实文件名 (含 001b 这类变体)。"""
        module = _load_module()
        on_disk = {p.name for p in ADR_DIR.glob("ADR-*.md")}
        self.assertEqual({e.filename for e in module.collect_entries()}, on_disk)

    def test_wiki_link_escapes_pipe(self) -> None:
        """Obsidian wikilink 用竖线分隔显示名, 文件名含竖线时必须转义。"""
        module = _load_module()
        entry = module.Entry(1, "", "a|b", "标题", "✅ 已接受", "2026-01-01")
        self.assertNotIn("a|b", entry.wiki_link)
        self.assertIn("a\\|b", entry.wiki_link)

    def test_sorted_descending_by_number(self) -> None:
        module = _load_module()
        entries = module.collect_entries()
        numbers = [e.number for e in entries]
        self.assertEqual(numbers, sorted(numbers, reverse=True))

    def test_numbers_are_contiguous(self) -> None:
        """编号不应有断层 (ADR-040 缺失曾长期无人察觉)。"""
        module = _load_module()
        numbers = sorted({e.number for e in module.collect_entries()})
        gaps = [n for n in range(numbers[0], numbers[-1] + 1) if n not in numbers]
        self.assertEqual(gaps, [], f"ADR 编号存在断层: {gaps}")


class CliBehaviorTest(unittest.TestCase):
    """CLI 的实际行为 —— 通过子进程跑真实路径。"""

    def setUp(self) -> None:
        # 跨进程互斥: 本类会真改仓库里的 docs/adr/ADR.md(被测脚本按
        # 仓库相对路径定位索引, 无法注入临时路径)。pytest-xdist 下
        # 多 worker 并行时彼此看不到对方的 addCleanup, 实测 -n 8 下
        # 会互踩并留下 canary。按用例取锁, 失败路径也保证释放。
        lock_cm = _acquire_repo_mutation_lock()
        lock_cm.__enter__()
        self.addCleanup(lock_cm.__exit__, None, None, None)

    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=180,
        )

    def test_check_passes_on_committed_state(self) -> None:
        result = self._run("--check")
        self.assertEqual(
            result.returncode,
            0,
            f"仓库内索引应与 ADR 文件一致, 实际输出:\n{result.stdout}{result.stderr}",
        )

    def test_generation_is_idempotent(self) -> None:
        """连续两次生成不应产生差异 (否则每次提交都会改文件)。"""
        before = INDEX_PATH.read_text(encoding="utf-8")
        self._run()
        after = INDEX_PATH.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_check_detects_missing_row(self) -> None:
        """索引少一行时 --check 必须失败 —— 这是门禁的核心能力。"""
        backup = INDEX_PATH.read_text(encoding="utf-8")
        self.addCleanup(INDEX_PATH.write_text, backup, "utf-8")

        lines = backup.splitlines()
        trimmed = [ln for ln in lines if "ADR-050-phase-33b9" not in ln]
        INDEX_PATH.write_text("\n".join(trimmed) + "\n", encoding="utf-8")

        result = self._run("--check")
        self.assertEqual(result.returncode, 1, "索引缺行时 --check 应退出 1")
        self.assertIn("generate_adr_index.py", result.stdout + result.stderr)

    def test_check_detects_unindexed_new_adr(self) -> None:
        """新增 ADR 但未更新索引时 --check 必须失败。"""
        canary = ADR_DIR / "ADR-063-canary-tmp.md"
        backup = INDEX_PATH.read_text(encoding="utf-8")
        self.addCleanup(canary.unlink)
        self.addCleanup(INDEX_PATH.write_text, backup, "utf-8")

        canary.write_text("# ADR-063: canary\n\n## 状态\n接受\n\n## 日期\n2026-10-02\n", encoding="utf-8")
        result = self._run("--check")
        self.assertEqual(result.returncode, 1, "新增未登记 ADR 时 --check 应退出 1")

    def test_dry_run_does_not_write(self) -> None:
        backup = INDEX_PATH.read_text(encoding="utf-8")
        self.addCleanup(INDEX_PATH.write_text, backup, "utf-8")
        result = self._run("--dry-run")
        self.assertEqual(result.returncode, 0)
        self.assertIn("BEGIN GENERATED ADR INDEX", result.stdout)
        self.assertEqual(INDEX_PATH.read_text(encoding="utf-8"), backup)


if __name__ == "__main__":
    unittest.main()
