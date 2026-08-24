"""rule_docs_mapper 回归测试（覆盖率门禁提升配套）。

覆盖此前 0% 的规则-文档联动模块的纯函数路径：
frontmatter/标题/文件名关键词提取、规则关键词提取、规则→文档匹配。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.rule_docs_mapper import (
    _extract_filename_keywords,
    _extract_frontmatter_keywords,
    _extract_title_keywords,
    _match_rule_to_docs,
    extract_keywords_from_docs,
    extract_keywords_from_rule,
)


class TestFrontmatterKeywords:
    def test_tags_list_json(self) -> None:
        fm = 'tags: ["python", "security"]\ntitle: x'
        assert _extract_frontmatter_keywords(fm) == ["python", "security"]

    def test_tags_comma_separated(self) -> None:
        fm = "tags: ruff, lint, style"
        assert _extract_frontmatter_keywords(fm) == ["ruff", "lint", "style"]

    def test_category_like_keys(self) -> None:
        fm = "category: governance\ndomain: quality\nunknown: skip"
        kws = _extract_frontmatter_keywords(fm)
        assert "governance" in kws
        assert "quality" in kws
        assert "skip" not in kws

    def test_invalid_json_tags_ignored(self) -> None:
        fm = "tags: [broken"
        assert _extract_frontmatter_keywords(fm) == []


class TestTitleKeywords:
    def test_headings_extracted(self) -> None:
        content = "# Main Title\n## Section Two\nbody text\n### Sub Section"
        kws = _extract_title_keywords(content)
        assert "main title" in kws
        assert "section two" in kws
        assert "sub section" in kws

    def test_long_words_split(self) -> None:
        kws = _extract_title_keywords("# Quality Gates Guide")
        assert "quality" in kws and "gates" in kws and "guide" in kws


class TestFilenameKeywords:
    def test_stem_words(self, tmp_path: Path) -> None:
        f = tmp_path / "code-review-checklist.md"
        assert _extract_filename_keywords(f) == ["code-review-checklist"]


class TestExtractFromDocs:
    def test_scans_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "guide.md").write_text(
            "---\ntags: [testing]\n---\n# Testing Guide\ncontent",
            encoding="utf-8",
        )
        # PROJECT_ROOT 是模块常量，relative_to 会失败于 tmp_path 外部目录；
        # 直接验证函数在非项目目录下的行为：跳过不可相对化的文件或正常返回。

        from tools.scripts.rules_engine import rule_docs_mapper

        original = rule_docs_mapper.PROJECT_ROOT
        rule_docs_mapper.PROJECT_ROOT = tmp_path
        try:
            result = extract_keywords_from_docs(tmp_path)
        finally:
            rule_docs_mapper.PROJECT_ROOT = original
        assert "guide.md" in result or result == {}
        assert any("testing" in kw for kw in result.get("guide.md", []))

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert extract_keywords_from_docs(tmp_path) == {}


class TestRuleKeywords:
    def test_language_expansion(self) -> None:
        kws = extract_keywords_from_rule("py-bare-except", {})
        assert "py" in kws
        assert "python" in kws
        assert "bare" in kws and "except" in kws

    def test_rule_fields_words(self) -> None:
        data = {"name": "missing-type-hints", "message": "Add type hints to public functions"}
        kws = extract_keywords_from_rule("py-missing-type-hints", data)
        assert "missing" in kws
        assert "public" in kws


class TestMatchRuleToDocs:
    def test_top3_and_min_overlap(self) -> None:
        doc_keywords = {
            "docs/a.md": ["python", "security", "bandit"],
            "docs/b.md": ["unrelated", "stuff"],
            "docs/c.md": ["python", "rust"],
        }
        result = _match_rule_to_docs("py-security-scan", {}, doc_keywords)
        paths = [d["path"] for d in result]
        assert "docs/a.md" in paths
        assert "docs/b.md" not in paths  # 重叠不足 2 被过滤

    def test_builtin_mapping_merged(self) -> None:
        from tools.scripts.rules_engine.rule_docs_mapper import BUILTIN_MAPPINGS

        if not BUILTIN_MAPPINGS:
            return
        rule_id = next(iter(BUILTIN_MAPPINGS))
        result = _match_rule_to_docs(rule_id, {}, {})
        builtin_paths = {b["path"] for b in BUILTIN_MAPPINGS[rule_id]}
        got_paths = {d["path"] for d in result}
        assert builtin_paths <= got_paths
