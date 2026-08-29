"""Unit tests for tools/scripts/link_efficiency_cases.py internals.

补充 tests/test_link_efficiency_cases.py (仅 CLI 子进程测试) 的不足，
直接 import 模块函数做单元测试，提升覆盖率从 0% 到 80%+。

测试范围:
- _extract_keywords (frontmatter + H1 标题)
- _match_score (alias 展开 + 字符串匹配)
- _has_link (字符串包含检测)
- _should_skip (TEMPLATE/README 排除)
- _collect_ai_to_case_links (主链接生成)
- _collect_case_to_ai_links (反向链接生成)
- _apply_changes (文件写入 + 段插入)
- _print_plan (输出格式)
- main (CLI 入口)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tools.scripts import link_efficiency_cases as link_mod

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "scripts" / "link_efficiency_cases.py"

# Ensure tools package is importable (in case conftest didn't run yet)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestExtractKeywords:
    """_extract_keywords: frontmatter tags + H1 关键词。"""

    def test_extracts_from_frontmatter_tags(self, tmp_path: Path) -> None:
        """frontmatter tags 应被提取。"""
        f = tmp_path / "doc.md"
        f.write_text("---\ntags: ['python', 'review']\n---\n# Title\n")
        kws = link_mod._extract_keywords(f)
        assert "python" in kws
        assert "review" in kws

    def test_extracts_from_h1(self, tmp_path: Path) -> None:
        """H1 标题应被拆分提取。"""
        f = tmp_path / "doc.md"
        f.write_text("# Code Review Best Practices\n")
        kws = link_mod._extract_keywords(f)
        assert "code" in kws
        assert "review" in kws
        assert "best" in kws

    def test_returns_empty_for_empty_file(self, tmp_path: Path) -> None:
        """空文件返回空集合。"""
        f = tmp_path / "empty.md"
        f.write_text("")
        assert link_mod._extract_keywords(f) == set()

    def test_short_words_excluded(self, tmp_path: Path) -> None:
        """长度 ≤ 2 的词被排除 (避免噪声)。"""
        f = tmp_path / "doc.md"
        f.write_text("# a i do good\n")
        kws = link_mod._extract_keywords(f)
        assert "a" not in kws
        assert "i" not in kws
        assert "good" in kws


class TestMatchScore:
    """_match_score: 关键词重叠 + alias 展开。"""

    def test_exact_match_score_2(self) -> None:
        """完全相同关键词每对得 2 分。"""
        score = link_mod._match_score({"python", "review"}, {"python", "review"})
        assert score == 4  # 2 pairs × 2

    def test_alias_match_score_1(self) -> None:
        """alias 组内匹配得 1 分。"""
        # 'review' 和 'code-review' 在同一个 alias 组
        score = link_mod._match_score({"review"}, {"code-review"})
        assert score == 1

    def test_no_match_score_0(self) -> None:
        """无交集得 0 分。"""
        assert link_mod._match_score({"python"}, {"javascript"}) == 0

    def test_empty_sets_score_0(self) -> None:
        """空集合得 0 分。"""
        assert link_mod._match_score(set(), set()) == 0


class TestHasLink:
    """_has_link: 字符串包含检测。"""

    def test_finds_existing_link(self) -> None:
        """链接名出现则返回 True。"""
        assert link_mod._has_link("See [api-design](api-design.md) for details.", "api-design") is True

    def test_returns_false_for_absent_link(self) -> None:
        """链接名未出现返回 False。"""
        assert link_mod._has_link("No links here.", "missing") is False


class TestShouldSkip:
    """_should_skip: TEMPLATE / README 排除。"""

    def test_skip_template_prefix(self, tmp_path: Path) -> None:
        """TEMPLATE-*.md 应跳过。"""
        f = tmp_path / "TEMPLATE-community.md"
        assert link_mod._should_skip(f) is True

    def test_skip_readme(self, tmp_path: Path) -> None:
        """README.md 应跳过。"""
        f = tmp_path / "README.md"
        assert link_mod._should_skip(f) is True

    def test_keep_normal_file(self, tmp_path: Path) -> None:
        """普通 case-study 不跳过。"""
        f = tmp_path / "api-design.md"
        assert link_mod._should_skip(f) is False


class TestCollectAiToCaseLinks:
    """_collect_ai_to_case_links: ai-*.md → case-studies 链接生成。

    使用 monkeypatch 把 REPO_ROOT 指向 tmp_path，避免污染真实仓库。
    """

    def test_generates_link_for_matching_keywords(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """关键词匹配时生成链接。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        ai = tmp_path / "ai_test_a.md"
        case = tmp_path / "case_test_a.md"
        ai.write_text("# Empty\n")
        case.write_text("# Empty\n")
        ai_files = {ai: {"python", "review"}}
        case_files = {case: {"python", "review"}}
        changes = link_mod._collect_ai_to_case_links(ai_files, case_files, min_score=2)
        assert len(changes) == 1
        file_, header, line = changes[0]
        assert file_ == ai
        assert header == "## 相关案例"
        assert "case_test_a.md" in line

    def test_skips_template(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TEMPLATE 文件被跳过。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        ai = tmp_path / "ai_t.md"
        case = tmp_path / "TEMPLATE-x.md"
        ai.write_text("# Empty\n")
        ai_files = {ai: {"python"}}
        case_files = {case: {"python"}}
        changes = link_mod._collect_ai_to_case_links(ai_files, case_files, min_score=1)
        assert changes == []

    def test_below_min_score_filtered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """低于 min_score 的不生成。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        ai = tmp_path / "ai_b.md"
        case = tmp_path / "case_b.md"
        ai.write_text("# Empty\n")
        ai_files = {ai: {"python"}}
        case_files = {case: {"javascript"}}
        changes = link_mod._collect_ai_to_case_links(ai_files, case_files, min_score=2)
        assert changes == []


class TestCollectCaseToAiLinks:
    """_collect_case_to_ai_links: case-studies → ai-*.md 反向链接。"""

    def test_generates_reverse_link(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """case → ai 链接生成。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        ai = tmp_path / "ai_rev.md"
        case = tmp_path / "case_rev.md"
        ai.write_text("# Empty\n")
        case.write_text("# Empty\n")
        ai_files = {ai: {"python"}}
        case_files = {case: {"python"}}
        changes = link_mod._collect_case_to_ai_links(ai_files, case_files, min_score=2)
        assert len(changes) == 1
        file_, header, line = changes[0]
        assert file_ == case
        assert header == "## 相关方法论"
        assert "ai_rev.md" in line


class TestApplyChanges:
    """_apply_changes: 文件修改 + 段插入。"""

    def test_inserts_new_header(self, tmp_path: Path) -> None:
        """新文件插入新段。"""
        f = tmp_path / "doc.md"
        f.write_text("original content")
        changes = [(f, "## 新段", "- line 1")]
        count = link_mod._apply_changes(changes)
        assert count == 1
        content = f.read_text()
        assert "## 新段" in content
        assert "line 1" in content

    def test_appends_to_existing_header(self, tmp_path: Path) -> None:
        """已有段下追加链接（不重复插入段）。"""
        f = tmp_path / "doc.md"
        f.write_text("## 已有段\n\nold content")
        changes = [(f, "## 已有段", "- new line")]
        link_mod._apply_changes(changes)
        content = f.read_text()
        # 段头只出现 1 次
        assert content.count("## 已有段") == 1
        assert "new line" in content
        assert "old content" in content

    def test_dedup_same_link(self, tmp_path: Path) -> None:
        """相同链接不重复添加。"""
        f = tmp_path / "doc.md"
        f.write_text("## 段\n\n- same line")
        changes = [(f, "## 段", "- same line")]
        link_mod._apply_changes(changes)
        content = f.read_text()
        assert content.count("same line") == 1


class TestPrintPlan:
    """_print_plan: 输出格式。"""

    def test_prints_summary(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """打印变更统计。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        changes = [(tmp_path / "a.md", "## H", "- line")]
        link_mod._print_plan(changes, ai_count=2, case_count=3)
        out = capsys.readouterr().out
        assert "将补全 1 处" in out
        assert "2 ai-docs" in out
        assert "3 cases" in out

    def test_truncates_long_lists(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """> 10 条变更时省略。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        changes = [(tmp_path / f"f{i}.md", "## H", f"- line {i}") for i in range(15)]
        link_mod._print_plan(changes, ai_count=5, case_count=10)
        out = capsys.readouterr().out
        assert "还有 5 条" in out


class TestMain:
    """main: CLI 入口集成测试。"""

    def test_missing_dir_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """目录不存在时返回 1。"""
        monkeypatch.setattr(link_mod, "REPO_ROOT", Path("/nonexistent/abc"))
        monkeypatch.setattr(link_mod, "EFFICIENCY_DIR", Path("/nonexistent/abc/docs"))
        monkeypatch.setattr(link_mod, "CASE_STUDIES_DIR", Path("/nonexistent/abc/cases"))
        monkeypatch.setattr("sys.argv", ["link_efficiency_cases"])
        assert link_mod.main() == 1

    def test_dry_run_does_not_modify(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--dry-run 不修改文件。"""
        eff = tmp_path / "docs" / "efficiency"
        case = tmp_path / "case-studies"
        eff.mkdir(parents=True)
        case.mkdir(parents=True)
        (eff / "ai-test.md").write_text("---\ntags: ['python']\n---\n# Test\n")
        (case / "test-case.md").write_text("---\ntags: ['python']\n---\n# Test\n")
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(link_mod, "EFFICIENCY_DIR", eff)
        monkeypatch.setattr(link_mod, "CASE_STUDIES_DIR", case)
        monkeypatch.setattr("sys.argv", ["link_efficiency_cases", "--dry-run"])
        rc = link_mod.main()
        assert rc == 0
        # 文件应未被修改（无 ## 相关案例 段）
        assert "## 相关案例" not in (eff / "ai-test.md").read_text()

    def test_no_changes_returns_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """无匹配时返回 0。"""
        eff = tmp_path / "docs" / "efficiency"
        case = tmp_path / "case-studies"
        eff.mkdir(parents=True)
        case.mkdir(parents=True)
        (eff / "ai-empty.md").write_text("# Empty\n")
        (case / "empty-case.md").write_text("# Empty\n")
        monkeypatch.setattr(link_mod, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(link_mod, "EFFICIENCY_DIR", eff)
        monkeypatch.setattr(link_mod, "CASE_STUDIES_DIR", case)
        monkeypatch.setattr("sys.argv", ["link_efficiency_cases", "--min-score", "99"])
        assert link_mod.main() == 0
