import json
import tempfile
import unittest
from pathlib import Path

from tools.scripts.check_doc_code_refs import (
    _CODE_PATH_RE,
    _iter_docs,
    _load_allowlist,
    scan_docs,
)


class TestRepoAllowlist:
    """仓库自带的豁免清单必须结构合法（否则失效引用会被静默放过或误报）。"""

    def test_repo_allowlist_is_valid(self) -> None:
        """`.jcode/doc-ref-allowlist.json` 存在且每条都有 path + reason。"""
        repo_allowlist = Path(__file__).resolve().parents[1] / ".jcode" / "doc-ref-allowlist.json"
        assert repo_allowlist.is_file(), f"缺少豁免清单: {repo_allowlist}"

        data = json.loads(repo_allowlist.read_text(encoding="utf-8"))
        entries = data.get("allowlist")
        assert isinstance(entries, list) and entries, "豁免清单不能为空"

        for entry in entries:
            assert isinstance(entry.get("path"), str) and entry["path"].strip()
            assert isinstance(entry.get("reason"), str) and entry["reason"].strip(), (
                f"豁免项缺少原因: {entry.get('path')}"
            )


class TestCheckDocCodeRefs(unittest.TestCase):
    """D-02: 文档中仓库代码路径引用的存在性校验。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write_doc(self, name: str, content: str) -> Path:
        doc_dir = self.root / "docs"
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc = doc_dir / name
        doc.write_text(content, encoding="utf-8")
        return doc

    def test_existing_repo_path_not_flagged(self) -> None:
        """引用仍存在（tools/scripts/check_metadata.py）→ 不报错。"""
        (self.root / "tools/scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "tools/scripts/check_metadata.py").write_text("# x\n", encoding="utf-8")
        doc = self._write_doc("valid.md", "入口脚本见 `tools/scripts/check_metadata.py`。")

        findings = scan_docs([doc], allowlist={}, root=self.root)
        self.assertEqual(findings, [])

    def test_missing_repo_path_flagged(self) -> None:
        """引用已不存在的路径 → 产出一条 Finding。"""
        doc = self._write_doc(
            "invalid.md", "旧入口 tools/scripts/legacy_analyzer.py 已移除。\n第二行 tools/scripts/other_missing.py。"
        )

        findings = scan_docs([doc], allowlist={}, root=self.root)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].ref, "tools/scripts/legacy_analyzer.py")
        self.assertEqual(findings[0].line, 1)
        self.assertEqual(findings[0].doc, "docs/invalid.md")
        self.assertEqual(findings[1].ref, "tools/scripts/other_missing.py")
        self.assertEqual(findings[1].line, 2)

    def test_placeholder_path_skipped(self) -> None:
        """占位路径（your_module.py）→ 不误报。"""
        doc = self._write_doc("placeholder.md", "自定义模块 tools/scripts/your_module.py 待实现。")

        findings = scan_docs([doc], allowlist={}, root=self.root)
        self.assertEqual(findings, [])

    def test_allowlisted_ref_skipped(self) -> None:
        """豁免清单中的失效引用 → 不进入 findings（豁免而非放行检查）。"""
        doc = self._write_doc("allow.md", "旧路径 tools/scripts/deprecated_tool_xyz.py 已废弃。")

        findings = scan_docs(
            [doc], allowlist={"tools/scripts/deprecated_tool_xyz.py": "迁移至 adg cicd"}, root=self.root
        )
        self.assertEqual(findings, [])

    def test_non_repo_path_not_flagged(self) -> None:
        """普通示例文件名（main.py）不在检查范围内 → 不误报。"""
        doc = self._write_doc("plain.md", "入口是 main.py，模块是 app/core.py。")

        findings = scan_docs([doc], allowlist={}, root=self.root)
        self.assertEqual(findings, [])

    def test_regex_only_matches_repo_prefixed_paths(self) -> None:
        """正则只识别带顶层目录前缀的仓库路径。"""
        self.assertIsNotNone(_CODE_PATH_RE.search("运行 python tools/scripts/check_metadata.py"))
        self.assertIsNone(_CODE_PATH_RE.search("运行 main.py"))

    def test_iter_docs_expands_directory(self) -> None:
        """_iter_docs 在目录输入时递归收集 markdown 文件。"""
        docs_dir = self.root / "docs/api"
        docs_dir.mkdir(parents=True)
        (docs_dir / "cli.md").write_text("# cli\n", encoding="utf-8")
        (docs_dir / "sub").mkdir()
        (docs_dir / "sub" / "deep.md").write_text("# deep\n", encoding="utf-8")

        docs = _iter_docs(["docs/api"], root=self.root)
        self.assertEqual([d.name for d in docs], ["cli.md", "deep.md"])

    def test_load_allowlist_missing_file_returns_empty(self) -> None:
        """缺失的豁免清单文件 → 返回空字典（不 fail-open）。"""
        allowlist = _load_allowlist(self.root / "does_not_exist.json")
        self.assertEqual(allowlist, {})

    def test_load_allowlist_invalid_json_returns_empty(self) -> None:
        """损坏的豁免清单 → 返回空字典并告警（不崩溃）。"""
        bad = self.root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        allowlist = _load_allowlist(bad)
        self.assertEqual(allowlist, {})

    def test_load_allowlist_reads_entries(self) -> None:
        """合法豁免清单 → 按 path→reason 读取。"""
        good = self.root / "good.json"
        good.write_text(
            json.dumps({"allowlist": [{"path": "tools/scripts/old.py", "reason": "迁移至 adg"}]}),
            encoding="utf-8",
        )
        self.assertEqual(_load_allowlist(good), {"tools/scripts/old.py": "迁移至 adg"})


if __name__ == "__main__":
    unittest.main()
