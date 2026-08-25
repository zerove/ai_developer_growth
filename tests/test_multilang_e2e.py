"""M5：多语言/框架/项目端到端冒烟测试。

覆盖链路：语言探测 → 架构守卫 → MCP 工具返回 → 检索源码索引。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_search_server():
    spec = importlib.util.spec_from_file_location("ss_e2e", "scripts/search-server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mixed_project(tmp_path: Path) -> Path:
    """Go 主导 + Ruby 尾随的多语言项目。"""
    (tmp_path / "internal" / "domain").mkdir(parents=True)
    (tmp_path / "go.mod").write_text("module demo\n", encoding="utf-8")
    (tmp_path / "internal" / "domain" / "svc.go").write_text(
        'package domain\n\nimport "net/http"\n',  # domain 引 http → 违规
        encoding="utf-8",
    )
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "u.rb").write_text("puts 1\n", encoding="utf-8")
    return tmp_path


class TestArchitectureGuardE2E:
    """架构守卫多语言端到端。"""

    def test_go_violation_detected(self, mixed_project: Path) -> None:
        from tools.scripts.architecture_drift_guard import ArchitectureDriftGuard

        guard = ArchitectureDriftGuard(mixed_project)
        violations = guard.check_layering()
        assert any("domain" in str(v) or "http" in str(v) for v in violations), f"go 违规未被识别: {violations}"

    def test_ruby_scanned_with_rules(self, mixed_project: Path) -> None:
        from tools.scripts.architecture_drift_guard import ArchitectureDriftGuard

        guard = ArchitectureDriftGuard(mixed_project)
        guard.check_layering()
        # Ruby 现已具备分层规则，应进入 scanned 而非 unsupported
        assert "ruby" in [str(lang).lower() for lang in guard.scanned_languages]
        assert guard.unsupported_languages == []

    def test_scanned_languages_contains_go(self, mixed_project: Path) -> None:
        from tools.scripts.architecture_drift_guard import ArchitectureDriftGuard

        guard = ArchitectureDriftGuard(mixed_project)
        guard.check_layering()
        names = [str(lang).lower() for lang in guard.scanned_languages]
        assert any("go" in n for n in names)


class TestSearchSourceDocsE2E:
    """检索服务源码索引端到端。"""

    def test_extract_source_docs_multilang(self, tmp_path: Path) -> None:
        m = _load_search_server()
        # 构造多语言小项目
        (tmp_path / "a.go").write_text(
            "// This is a go doc comment line\n// Second meaningful comment here\n// Third one to pass threshold\npackage main\n",
            encoding="utf-8",
        )
        (tmp_path / "b.rb").write_text(
            "# Ruby comment with real content here\n# Another ruby documentation line\n# And a third ruby line ok\nputs 1\n",
            encoding="utf-8",
        )
        docs = m.extract_source_docs(tmp_path)
        ids = [d.id for d in docs]
        assert len(docs) == 2, f"应提取 go+rb 两份源码文档，实际 {ids}"

    def test_short_comments_filtered(self, tmp_path: Path) -> None:
        m = _load_search_server()
        (tmp_path / "x.go").write_text("// hi\n// yo\npackage main\n", encoding="utf-8")
        assert m.extract_source_docs(tmp_path) == []


class TestMCPTaskGraphSmoke:
    """MCP 工具注册冒烟：确认多语言守卫工具可被发现与调用。"""

    def test_guard_tool_in_registry(self) -> None:
        from tools.scripts.ai_native_mcp_server import TOOL_REGISTRY, AINativeMCPServer

        tool_names = [t["name"] if isinstance(t, dict) else t.name for t in TOOL_REGISTRY]
        assert "run_architecture_guard" in tool_names

        server = AINativeMCPServer()
        result = server.handle_tool_call("run_architecture_guard", {})
        assert result.get("status") == "success"
        assert "violations" in result
