"""测试 .jcode/scripts/governance-docs-validator.py。

该脚本此前零测试覆盖，却驱动两类 hook：
- on_commit  / governance-docs-check   -> validate
- on_pr       / governance-index-check  -> check-index
- docs-governance.yml 的 5 个门禁中的 2 个

测试重点：
1. extract_frontmatter 是纯函数，逐分支覆盖
2. validate / check_index 的失败检测能力（用临时项目根注入缺陷文档）
3. main() 的 action 分派与未知 action 处理
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"


def _load(name: str, alias: str):
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(alias, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gdv():
    return _load("governance-docs-validator", "jcode_gov_docs_validator")


# ── extract_frontmatter（纯函数） ─────────────────────────────────────


class TestExtractFrontmatter:
    def test_no_frontmatter_returns_content_unchanged(self, gdv) -> None:
        content = "# Title\n\nbody text"
        fm, body = gdv.extract_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_unterminated_frontmatter(self, gdv) -> None:
        content = "---\ntitle: x\n\n# no closing delimiter"
        fm, body = gdv.extract_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_parses_simple_fields(self, gdv) -> None:
        fm, body = gdv.extract_frontmatter('---\ntitle: "T"\ncategory: 效率层\n---\n\n正文')
        assert fm["title"] == "T"
        assert fm["category"] == "效率层"
        assert "正文" in body
        assert "title" not in body

    def test_strips_quotes_and_whitespace(self, gdv) -> None:
        fm, _ = gdv.extract_frontmatter("---\ntitle: 'Quoted'\ndifficulty:  中级 \n---\n")
        assert fm["title"] == "Quoted"
        assert fm["difficulty"] == "中级"

    def test_value_containing_colon_is_preserved(self, gdv) -> None:
        """`description: a: b` 只应按第一个冒号切分。"""
        fm, _ = gdv.extract_frontmatter("---\ndescription: see also: here\n---\n")
        assert fm["description"] == "see also: here"

    def test_empty_frontmatter(self, gdv) -> None:
        fm, _ = gdv.extract_frontmatter("---\n---\nbody")
        assert fm == {}


# ── validate ────────────────────────────────────────────────────────

_GOOD_DOC = """---
title: Good Doc (English Suffix)
description: 一个合规文档
category: 效率层
tags:
  - a
difficulty: 中级
---

# 标题

## 导航

内容

## 相关文档

内容

## 第三节

内容
"""


def _write(tmp_path: Path, rel: str, content: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


class TestValidate:
    def _run(self, gdv, tmp_path: Path, docs: list[str]):
        with patch.object(gdv, "get_project_root", return_value=tmp_path), patch.object(gdv, "GOVERNANCE_DOCS", docs):
            return gdv.validate()

    def test_compliant_doc_passes(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "docs/efficiency/good.md", _GOOD_DOC)
        assert self._run(gdv, tmp_path, ["docs/efficiency/good.md"]) == 0
        assert "[通过]" in capsys.readouterr().out

    def test_missing_file_detected(self, gdv, tmp_path: Path, capsys) -> None:
        assert self._run(gdv, tmp_path, ["docs/efficiency/nope.md"]) == 1
        assert "Missing:" in capsys.readouterr().out

    def test_missing_frontmatter_detected(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "docs/efficiency/x.md", "# 没有 frontmatter\n")
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1
        assert "frontmatter" in capsys.readouterr().out

    def test_each_required_field_is_enforced(self, gdv, tmp_path: Path, capsys) -> None:
        """逐个删除必填字段，都必须被检出。"""
        for field in ("title", "description", "category", "tags", "difficulty"):
            content = "\n".join(line for line in _GOOD_DOC.splitlines() if not line.startswith(f"{field}:"))
            _write(tmp_path, "docs/efficiency/x.md", content)
            assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1, f"{field} 未被强制"
            assert field in capsys.readouterr().out

    def test_title_must_end_with_parenthetical(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "docs/efficiency/x.md", _GOOD_DOC.replace("(English Suffix)", "无后缀"))
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1
        assert "parentheses" in capsys.readouterr().out

    @pytest.mark.parametrize("bad_category", ["分析报告", "计划", "efficiency", "知识库"])
    def test_invalid_category_detected(self, gdv, tmp_path: Path, capsys, bad_category: str) -> None:
        """这 4 个值在仓库里真实存在过，但不在白名单内。"""
        _write(tmp_path, "docs/efficiency/x.md", _GOOD_DOC.replace("效率层", bad_category))
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1
        assert "Invalid category" in capsys.readouterr().out

    @pytest.mark.parametrize("valid_category", ["认知层", "学习层", "效率层", "工具层", "治理层"])
    def test_valid_categories_accepted(self, gdv, tmp_path: Path, valid_category: str) -> None:
        _write(tmp_path, "docs/efficiency/x.md", _GOOD_DOC.replace("效率层", valid_category))
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 0

    def test_missing_navigation_detected(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "docs/efficiency/x.md", _GOOD_DOC.replace("## 导航", "## 其他"))
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1
        assert "navigation" in capsys.readouterr().out

    def test_missing_related_docs_detected(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "docs/efficiency/x.md", _GOOD_DOC.replace("## 相关文档", "## 别的"))
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1
        assert "related docs" in capsys.readouterr().out

    def test_too_few_sections_detected(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "docs/efficiency/x.md", _GOOD_DOC.split("## 第三节")[0])
        assert self._run(gdv, tmp_path, ["docs/efficiency/x.md"]) == 1
        assert "minimum 3" in capsys.readouterr().out

    def test_reports_every_offending_doc(self, gdv, tmp_path: Path, capsys) -> None:
        """不得只报第一个就停——多文档时问题数量必须准确。"""
        _write(tmp_path, "docs/efficiency/a.md", _GOOD_DOC)
        _write(tmp_path, "docs/efficiency/b.md", "# bad\n")
        _write(tmp_path, "docs/efficiency/c.md", "# bad\n")
        assert self._run(gdv, tmp_path, ["docs/efficiency/a.md", "docs/efficiency/b.md", "docs/efficiency/c.md"]) == 1
        out = capsys.readouterr().out
        assert "b.md" in out and "c.md" in out
        assert "a.md" not in out.split("All checks")[0].split("- b.md")[0].split("  - ")[-1]


# ── check_index ──────────────────────────────────────────────────────


class TestCheckIndex:
    def _run(self, gdv, tmp_path: Path, docs: list[str]):
        with patch.object(gdv, "get_project_root", return_value=tmp_path), patch.object(gdv, "GOVERNANCE_DOCS", docs):
            return gdv.check_index()

    def test_all_references_present(self, gdv, tmp_path: Path) -> None:
        _write(tmp_path, "GOVERNANCE.md", "见 ai-sdlc / full-cycle-workflow / quality-gates")
        assert self._run(gdv, tmp_path, ["docs/efficiency/ai-sdlc.md", "docs/efficiency/full-cycle-workflow.md"]) == 0

    def test_missing_reference_detected(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "GOVERNANCE.md", "只提到 ai-sdlc")
        assert self._run(gdv, tmp_path, ["docs/efficiency/ai-sdlc.md", "docs/efficiency/quality-gates.md"]) == 1
        out = capsys.readouterr().out
        assert "quality-gates" in out and "ai-sdlc" not in out.split("- ")[1]

    def test_absent_governance_md_is_error(self, gdv, tmp_path: Path, capsys) -> None:
        assert self._run(gdv, tmp_path, ["docs/efficiency/ai-sdlc.md"]) == 1
        assert "GOVERNANCE.md not found" in capsys.readouterr().out

    def test_optional_index_md_is_checked_when_present(self, gdv, tmp_path: Path, capsys) -> None:
        _write(tmp_path, "GOVERNANCE.md", "ai-sdlc")
        _write(tmp_path, "INDEX.md", "空索引")
        assert self._run(gdv, tmp_path, ["docs/efficiency/ai-sdlc.md"]) == 1
        assert "INDEX.md" in capsys.readouterr().out

    def test_absent_index_md_is_tolerated(self, gdv, tmp_path: Path) -> None:
        """INDEX.md 是可选的（项目可用 docs/MOC.md 替代），缺失不得报错。"""
        _write(tmp_path, "GOVERNANCE.md", "ai-sdlc")
        assert self._run(gdv, tmp_path, ["docs/efficiency/ai-sdlc.md"]) == 0

    def test_absent_claude_md_is_tolerated(self, gdv, tmp_path: Path) -> None:
        _write(tmp_path, "GOVERNANCE.md", "ai-sdlc")
        assert self._run(gdv, tmp_path, ["docs/efficiency/ai-sdlc.md"]) == 0


# ── sync_refs ────────────────────────────────────────────────────────


class TestSyncRefs:
    def test_inserts_governance_reference(self, gdv, tmp_path: Path) -> None:
        doc = "docs/efficiency/x.md"
        _write(tmp_path, doc, _GOOD_DOC)
        with patch.object(gdv, "get_project_root", return_value=tmp_path), patch.object(gdv, "GOVERNANCE_DOCS", [doc]):
            assert gdv.sync_refs() == 0
        assert "GOVERNANCE" in (tmp_path / doc).read_text(encoding="utf-8")

    def test_is_idempotent(self, gdv, tmp_path: Path) -> None:
        doc = "docs/efficiency/x.md"
        _write(tmp_path, doc, _GOOD_DOC)
        with patch.object(gdv, "get_project_root", return_value=tmp_path), patch.object(gdv, "GOVERNANCE_DOCS", [doc]):
            gdv.sync_refs()
            first = (tmp_path / doc).read_text(encoding="utf-8")
            gdv.sync_refs()
            assert (tmp_path / doc).read_text(encoding="utf-8") == first, "重复执行不应继续追加"

    def test_missing_file_is_skipped(self, gdv, tmp_path: Path) -> None:
        with (
            patch.object(gdv, "get_project_root", return_value=tmp_path),
            patch.object(gdv, "GOVERNANCE_DOCS", ["docs/efficiency/nope.md"]),
        ):
            assert gdv.sync_refs() == 0


# ── full / main ──────────────────────────────────────────────────────


class TestFullAndMain:
    def test_full_fails_when_a_subcheck_fails(self, gdv) -> None:
        with patch.object(gdv, "validate", return_value=1), patch.object(gdv, "check_index", return_value=0):
            assert gdv.full() == 1

    def test_full_passes_when_all_ok(self, gdv) -> None:
        with patch.object(gdv, "validate", return_value=0), patch.object(gdv, "check_index", return_value=0):
            assert gdv.full() == 0

    @pytest.mark.parametrize(
        ("action", "target"),
        [
            ("validate", "validate"),
            ("check-index", "check_index"),
            ("sync-refs", "sync_refs"),
            ("full", "full"),
        ],
    )
    def test_action_dispatch(self, gdv, tmp_path: Path, action: str, target: str) -> None:
        """验证 action 名 -> 函数的分派映射。

        必须打桩目标函数：sync-refs 会写文件，直接调用会污染真实仓库文档
        （此前该测试向 15 个治理文档各插入了一行 wikilink）。
        get_project_root 额外指向 tmp_path 作为第二道防线。
        """
        with (
            patch.object(gdv, target, return_value=0) as stub,
            patch.object(gdv, "get_project_root", return_value=tmp_path),
            patch.object(sys, "argv", ["governance-docs-validator.py", action]),
            pytest.raises(SystemExit) as exc,
        ):
            gdv.main()
        assert exc.value.code == 0
        stub.assert_called_once_with()

    def test_unknown_action_exits_nonzero(self, gdv, capsys) -> None:
        with patch.object(sys, "argv", ["governance-docs-validator.py", "nope"]):
            with pytest.raises(SystemExit) as exc:
                gdv.main()
        assert exc.value.code == 1
        assert "nope" in capsys.readouterr().out

    def test_no_action_exits_nonzero(self, gdv) -> None:
        with patch.object(sys, "argv", ["governance-docs-validator.py"]):
            with pytest.raises(SystemExit) as exc:
                gdv.main()
        assert exc.value.code == 1


class TestHookWiring:
    """hooks.json 里指向本脚本的 action 必须是它真实支持的名字。"""

    def test_hooks_json_actions_are_supported(self, gdv) -> None:
        import json

        cfg = json.loads((Path(__file__).resolve().parent.parent / ".jcode" / "hooks.json").read_text(encoding="utf-8"))
        supported = {"validate", "check-index", "sync-refs", "full"}
        for event, hooks in cfg["hooks"].items():
            for h in hooks:
                if h.get("skill") == "governance-docs-validator":
                    assert h["action"] in supported, f"{event}/{h['name']} 使用了不支持的 action: {h['action']}"
