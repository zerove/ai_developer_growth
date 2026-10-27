"""Tests for tools/scripts/_paths.py (仓库根与 frontmatter 解析)."""

from pathlib import Path

from tools.scripts._paths import REPO_ROOT, repo_root, resolve_repo_path, split_frontmatter


def test_split_frontmatter_basic() -> None:
    content = "---\ntitle: Test\ntags: ['AI', 'test']\n---\n\n# Body\n"
    fm, body = split_frontmatter(content)
    assert fm == {"title": "Test", "tags": "['AI', 'test']"}
    assert body == "# Body\n"


def test_split_frontmatter_without_block_returns_content() -> None:
    content = "# Title\n"
    fm, body = split_frontmatter(content)
    assert fm == {}
    assert body == content


def test_split_frontmatter_empty_block() -> None:
    fm, body = split_frontmatter("---\n---\n\nBody")
    assert fm == {}
    assert body == "Body"


def test_split_frontmatter_strips_quotes_and_ignores_comments() -> None:
    fm, _ = split_frontmatter('---\n# comment\ncategory: "效率层"\n---\nBody')
    assert fm == {"category": "效率层"}


def test_resolve_repo_path_is_cwd_independent(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    assert repo_root() == REPO_ROOT
    assert resolve_repo_path("docs") == REPO_ROOT / "docs"

    absolute = tmp_path / "x.md"
    assert resolve_repo_path(absolute) == absolute
