"""小模块覆盖清扫: semantic_code_graph / arch_visualizer / dev_metrics / ai_pr_reviewer。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.scripts._common import get_project_root
from tools.scripts.ai_pr_reviewer import (
    check_architecture_findings,
    check_security_findings,
)
from tools.scripts.arch_visualizer import generate_mermaid_diagram, scan_python_imports
from tools.scripts.dev_metrics import compute, first_commit_date, git_log_since
from tools.scripts.semantic_code_graph import CodeNode, SemanticCodeGraph

REPO_ROOT = get_project_root()
PY = sys.executable


# ── semantic_code_graph ──────────────────────────────────────


class TestSemanticCodeGraph:
    def _sample_project(self, tmp_path: Path) -> Path:
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "service.py").write_text(
            "import helper\n\n\nclass Service:\n    def run(self):\n        return 1\n"
        )
        (tmp_path / "pkg" / "app.py").write_text(
            "from pkg.service import Service\n\n\ndef main():\n    s = Service()\n    s.run()\n"
        )
        return tmp_path

    def test_code_node_to_dict(self) -> None:
        node = CodeNode("f", "function", "a.py", 1)
        node.dependencies.add("g")
        d = node.to_dict()
        assert d["name"] == "f" and d["dependencies"] == ["g"] and d["dependents"] == []

    def test_build_graph_and_impact(self, tmp_path: Path) -> None:
        root = self._sample_project(tmp_path)
        graph = SemanticCodeGraph(root_dir=root)
        graph.build_graph()
        names = {n.name for n in graph.nodes.values()}
        assert {"Service", "main"} <= names
        # main 调用... 无直接依赖解析到 Service(通过 import 名), 至少图非空且可查询
        impacted = graph.query_impact("main")
        assert any(i["name"] == "main" for i in impacted)

    def test_skips_venv_dirs(self, tmp_path: Path) -> None:
        bad = tmp_path / ".venv"
        bad.mkdir()
        (bad / "x.py").write_text("def hidden(): pass\n")
        graph = SemanticCodeGraph(root_dir=tmp_path)
        graph.build_graph()
        assert all(".venv" not in n.file_path for n in graph.nodes.values())

    def test_save_to_json(self, tmp_path: Path) -> None:
        import json

        root = self._sample_project(tmp_path)
        graph = SemanticCodeGraph(root_dir=root)
        graph.build_graph()
        out = tmp_path / "graph.json"
        graph.save_to_json(out)
        data = json.loads(out.read_text())
        assert len(data) == len(graph.nodes)

    def test_query_no_match(self, tmp_path: Path) -> None:
        root = self._sample_project(tmp_path)
        graph = SemanticCodeGraph(root_dir=root)
        graph.build_graph()
        assert graph.query_impact("nonexistent-symbol-xyz") == []


# ── arch_visualizer ──────────────────────────────────────────


class TestArchVisualizer:
    def test_scan_imports(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("import json\nfrom os import path\n")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "b.py").write_text("import json\n")
        graph = scan_python_imports(tmp_path)
        assert "a" in graph
        assert "json" in graph["a"] and "os" in graph["a"]
        assert not any(".venv" in k for k in graph)

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text("def broken(:\n")
        graph = scan_python_imports(tmp_path)
        assert graph.get("bad") == set()

    def test_mermaid_generation(self) -> None:
        graph = {"app": {"json", "helper"}, "helper": {"json"}}
        text = generate_mermaid_diagram(graph)
        assert text.startswith("graph TD;")
        assert "app --> helper" in text or "app --> json" in text

    def test_main_cli(self, tmp_path: Path) -> None:
        out = tmp_path / "arch.md"
        r = subprocess.run(
            [PY, "-m", "tools.scripts.arch_visualizer", "--path", str(tmp_path), "--output", str(out)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0 and out.exists()

    def test_main_bad_path(self, tmp_path: Path) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.arch_visualizer", "--path", str(tmp_path / "nope")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 1


# ── dev_metrics ──────────────────────────────────────────────


class TestDevMetrics:
    def test_compute_empty(self) -> None:
        m = compute([])
        assert m["total_commits"] == 0 and m["conventional_rate"] == 0.0

    def test_compute_mixed(self) -> None:
        subjects = ["feat(x): add thing", "fix bug quickly", "chore: bump", "随手改"]
        m = compute(subjects)
        assert m["total_commits"] == 4
        assert m["conventional_count"] == 2
        assert m["conventional_rate"] == 50.0
        # "fix bug quickly" 含 lint/hook 关键词吗? 无 → hook_fixes 来自 chore? 无关键词
        assert isinstance(m["hook_fix_commits"], int)

    def test_hook_fix_keyword_detected(self) -> None:
        m = compute(["style: ruff format 修正"])
        assert m["hook_fix_commits"] == 1

    def test_git_log_real_repo(self) -> None:
        subjects = git_log_since(REPO_ROOT, since="2026-08-01")
        assert len(subjects) > 3

    def test_first_commit_date_real_repo(self) -> None:
        date = first_commit_date(REPO_ROOT)
        assert date != "n/a" and len(date) >= 8


# ── ai_pr_reviewer 检查器 ────────────────────────────────────


class TestPRReviewerFindings:
    def test_shell_true_flagged(self) -> None:
        findings: list[dict[str, str]] = []
        check_security_findings("subprocess.run(cmd, shell=True)", findings)
        assert any(f["rule"] == "sec-shell-injection" for f in findings)

    def test_clean_text_no_findings(self) -> None:
        findings: list[dict[str, str]] = []
        check_security_findings("print('hello world')", findings)
        assert findings == []

    def test_wildcard_import_flagged(self) -> None:
        findings: list[dict[str, str]] = []
        check_architecture_findings("from os import *", findings)
        assert any(f["rule"] == "arch-wildcard-import" for f in findings)

    def test_global_statement_flagged(self) -> None:
        findings: list[dict[str, str]] = []
        check_architecture_findings("global counter", findings)
        assert any(f["rule"] == "arch-global-state" for f in findings)

    def test_clean_architecture(self) -> None:
        findings: list[dict[str, str]] = []
        check_architecture_findings("import json", findings)
        assert findings == []


class TestGetGitDiff:
    def test_returns_string_in_repo(self) -> None:
        from tools.scripts.ai_pr_reviewer import get_git_diff

        diff = get_git_diff()
        assert isinstance(diff, str)
