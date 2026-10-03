"""rule_docs_mapper 第二轮: 规则加载/匹配打分/build/rebuild/query/main。44%→85%+"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scripts.rules_engine import rule_docs_mapper as rdm


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """构造 docs + rules 目录结构, monkeypatch 模块级路径常量。"""
    docs = tmp_path / "docs"
    (docs / "learning").mkdir(parents=True)
    (docs / "security").mkdir(parents=True)
    (docs / "learning" / "python-basics.md").write_text(
        "---\ntags: [python, exceptions]\n---\n# Python Exceptions Guide\n\n## bare except pitfalls\n",
        encoding="utf-8",
    )
    (docs / "security" / "secure-coding.md").write_text(
        "---\ntags: [security]\n---\n# Secure Coding\n\n## eval is dangerous\n",
        encoding="utf-8",
    )
    # 规则目录: languages/python/rules.d/anti_patterns.yml
    lang = tmp_path / "ai-dev-framework" / "languages" / "python" / "rules.d"
    lang.mkdir(parents=True)
    (lang / "anti_patterns.yml").write_text(
        """
anti_patterns:
  - id: py-bare-except
    name: Bare except clause
    severity: error
    category: reliability
    message: avoid bare except
  - id: py-eval-exec
    name: eval usage
    severity: error
    category: security
""",
        encoding="utf-8",
    )
    rdm.PROJECT_ROOT = tmp_path  # type: ignore[misc]
    rdm.DOCS_DIR = docs
    rdm.CASE_STUDIES_DIR = tmp_path / "case-studies"
    rdm.MAPPING_CACHE = tmp_path / ".jcode" / "rule-docs-mapping.json"
    return tmp_path


def _patch_scan(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    """让 _scan_documents 只扫 workspace/docs, 规避默认参数绑定真实仓库路径的问题。"""
    real_extract = rdm.extract_keywords_from_docs

    def fake_scan(docs_dir: Path, case_studies: bool) -> dict[str, list[str]]:
        kw = real_extract(workspace / "docs")
        cs = workspace / "case-studies"
        if case_studies and cs.exists():
            kw.update(real_extract(cs))
        return kw

    monkeypatch.setattr(rdm, "_scan_documents", fake_scan)


class TestSimpleParser:
    def test_simple_parse_without_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.yml"
        f.write_text(
            "# comment\n- id: rule-a\n  name: Rule A\n  severity: error\n  unknown_key: skip\n- id: rule-b\n",
            encoding="utf-8",
        )
        rules = rdm._simple_parse_rules(f)
        assert len(rules) == 2
        assert rules[0]["id"] == "rule-a" and rules[0]["name"] == "Rule A"
        assert "unknown_key" not in rules[0]

    def test_load_yml_success(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.yml"
        f.write_text("anti_patterns:\n  - id: x\n", encoding="utf-8")
        assert rdm._load_rules_from_yml(f)[0]["id"] == "x"

    def test_load_missing_and_corrupt(self, tmp_path: Path) -> None:
        assert rdm._load_rules_from_yml(tmp_path / "nope.yml") == []
        bad = tmp_path / "bad.yml"
        bad.write_text("{ broken: [", encoding="utf-8")
        assert rdm._load_rules_from_yml(bad) == []


class TestLoadAllRules:
    def test_languages_and_frameworks_merged(self, workspace: Path) -> None:
        fw = workspace / "ai-dev-framework" / "frameworks" / "django" / "rules.d"
        fw.mkdir(parents=True)
        (fw / "anti_patterns.yml").write_text("anti_patterns:\n  - id: dj-raw-sql\n", encoding="utf-8")
        all_rules = rdm._load_all_rules(workspace / "ai-dev-framework" / "languages")
        assert {"py-bare-except", "py-eval-exec", "dj-raw-sql"} <= set(all_rules)

    def test_missing_dir_returns_empty(self, workspace: Path) -> None:
        assert rdm._load_all_rules(workspace / "nonexistent") == {}


class TestMatching:
    def test_match_scores_overlap(self, workspace: Path) -> None:
        doc_kw = {
            "docs/learning/python-basics.md": ["python", "exceptions", "bare", "except"],
            "docs/security/secure-coding.md": ["eval", "security", "dangerous"],
        }
        matches = rdm._match_rule_to_docs("py-bare-except", {"name": "Bare except"}, doc_kw)
        assert matches[0]["path"] == "docs/learning/python-basics.md"

    def test_low_overlap_filtered(self, workspace: Path) -> None:
        doc_kw = {"docs/x.md": ["python"]}  # 只有 1 个重叠 < 2
        matches = rdm._match_rule_to_docs("unknown-rule-xyz", {}, doc_kw)
        assert matches == []

    def test_builtin_dedup(self, workspace: Path) -> None:
        doc_kw = {"docs/mindset/error-handling.md": ["bare", "except", "python"]}
        matches = rdm._match_rule_to_docs("py-bare-except", {"name": "bare"}, doc_kw)
        builtin_paths = [d["path"] for d in rdm.BUILTIN_MAPPINGS["py-bare-except"]]
        merged = [m["path"] for m in matches]
        assert len(merged) == len(set(merged)) and set(builtin_paths) <= set(merged)


class TestBuildAndQuery:
    def test_build_mapping_end_to_end(self, workspace: Path) -> None:
        mapping = rdm.build_mapping(rule_dir=workspace / "ai-dev-framework" / "languages", docs_dir=rdm.DOCS_DIR)
        assert "py-bare-except" in mapping
        assert any("python-basics" in d["path"] for d in mapping["py-bare-except"])

    def test_case_studies_included_when_exists(self, workspace: Path) -> None:
        cs = workspace / "case-studies"
        cs.mkdir()
        (cs / "fixing-bare-except.md").write_text("# fixing bare except in python\n", encoding="utf-8")
        mapping = rdm.build_mapping(rule_dir=workspace / "ai-dev-framework" / "languages", docs_dir=rdm.DOCS_DIR)
        paths = [d["path"] for d in mapping.get("py-bare-except", [])]
        assert any("case-studies" in p for p in paths)

    def test_rebuild_writes_cache(
        self, workspace: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_scan(monkeypatch, workspace)
        mapping = rdm.rebuild_mapping(
            rule_dir=workspace / "ai-dev-framework" / "languages", output_path=rdm.MAPPING_CACHE
        )
        cache = rdm.MAPPING_CACHE
        assert cache.exists()
        assert json.loads(cache.read_text(encoding="utf-8")) == mapping
        assert "Mapping saved" in capsys.readouterr().out

    def test_query_found_and_not_found(self, workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_scan(monkeypatch, workspace)
        cache = rdm.MAPPING_CACHE
        rdm.rebuild_mapping(rule_dir=workspace / "ai-dev-framework" / "languages", output_path=cache)
        hits = rdm.query_mapping("py-bare-except", mapping_path=cache)
        assert hits and hits[0]["path"]
        assert rdm.query_mapping("ghost-rule", mapping_path=cache) == []

    def test_query_missing_cache(self, workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
        missing = workspace / "nonexistent-cache.json"
        assert rdm.query_mapping("any", mapping_path=missing) == []
        assert "rebuild first" in capsys.readouterr().out

    def test_default_args_resolve_mapping_cache_at_call_time(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """省略 mapping_path/output_path 时必须在**调用时**读 MAPPING_CACHE。

        若写成 `mapping_path: Path = MAPPING_CACHE`, 默认值会在**导入时**
        被固化成仓库真实路径, 于是 monkeypatch 模块属性完全无效 ——
        测试悄悄去读工作区的 `.jcode/rule-docs-mapping.json`(一个未跟踪
        的生成物), 变成依赖工作区状态的随机失败。
        同一个陷阱已在本文件 `_scan_documents` 上出现过一次, 那里是用
        `_patch_scan` 绕过去的; 这里把默认参数绑定本身修掉, 并锁住该行为。
        """
        _patch_scan(monkeypatch, workspace)
        cache = rdm.MAPPING_CACHE
        assert cache == workspace / ".jcode" / "rule-docs-mapping.json", "夹具未把缓存指向 tmp_path"
        # 仓库真实缓存可能不存在、也可能缺该规则, 两者都不应影响这里。
        rdm.query_mapping("py-bare-except")
        rdm.rebuild_mapping()
        assert cache.exists(), "rebuild_mapping 未写入 monkeypatch 后的缓存路径"
        assert "py-bare-except" in json.loads(cache.read_text(encoding="utf-8"))


class TestMain:
    def _patch_build(self, monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
        real_build = rdm.build_mapping
        monkeypatch.setattr(
            rdm,
            "build_mapping",
            lambda rule_dir=None, **kw: real_build(
                rule_dir=workspace / "ai-dev-framework" / "languages",
                docs_dir=rdm.DOCS_DIR,
            ),
        )
        _patch_scan(monkeypatch, workspace)

    def test_main_query_hit(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_build(monkeypatch, workspace)
        rdm.rebuild_mapping(rule_dir=workspace / "ai-dev-framework" / "languages", output_path=rdm.MAPPING_CACHE)
        monkeypatch.setattr(rdm, "MAPPING_CACHE", rdm.MAPPING_CACHE)
        monkeypatch.setattr("sys.argv", ["rule_docs_mapper.py", "--query", "py-bare-except"])
        code = rdm.main()
        out = capsys.readouterr().out
        assert code == 0 and "Docs related to" in out

    def test_main_query_miss_exit_1(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_build(monkeypatch, workspace)
        rdm.rebuild_mapping(rule_dir=workspace / "ai-dev-framework" / "languages", output_path=rdm.MAPPING_CACHE)
        monkeypatch.setattr("sys.argv", ["rule_docs_mapper.py", "--query", "no-such-rule"])
        assert rdm.main() == 1
        assert "No docs found" in capsys.readouterr().out

    def test_main_rebuild_json(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch_build(monkeypatch, workspace)
        monkeypatch.setattr("sys.argv", ["rule_docs_mapper.py", "--rebuild", "--json"])
        code = rdm.main()
        out = capsys.readouterr().out
        parsed = json.loads(out[out.index("{") :])
        assert code == 0 and isinstance(parsed, dict)

    def test_main_help_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr("sys.argv", ["rule_docs_mapper.py"])
        assert rdm.main() == 1
