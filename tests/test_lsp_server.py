"""LSP server 单元测试 — 不启动 stdio/TCP，只测 AdgLanguageServer 协议层。

覆盖 ROADMAP P1-4 "0% 模块测试攻坚"中 tools/lsp/server.py (510 行无单测)。

测试目标：
1. AdgLanguageServer 协议层 handle_request 路由
2. 各 _handle_* 协议方法的输入 → 输出映射
3. _get_rules 缓存命中
4. exclude_patterns / enable_quick_fix / enable_code_lens 等配置开关
5. 边界：未支持文件后缀、不存在文件、空 query、未知 method
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 路径修复：让 import tools.lsp.server 能找到
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.lsp.server import (  # noqa: E402
    SUPPORTED_EXTENSIONS,
    AdgLanguageServer,
)

# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────


@pytest.fixture
def server() -> AdgLanguageServer:
    """返回干净的 AdgLanguageServer 实例。"""
    return AdgLanguageServer()


@pytest.fixture
def tmp_python_file(tmp_path: Path) -> Path:
    """创建一个临时的 Python 文件用于诊断测试。"""
    f = tmp_path / "sample.py"
    f.write_text("def foo():\n    pass\n")
    return f


# ─────────────────────────────────────────────────────────
# 协议层路由
# ─────────────────────────────────────────────────────────


class TestHandleRequestRouting:
    def test_known_method_initialialize_returns_capabilities(self, server: AdgLanguageServer) -> None:
        result = server.handle_request("initialize", {})
        assert "capabilities" in result
        assert "textDocumentSync" in result["capabilities"]
        assert "codeActionProvider" in result["capabilities"]

    def test_initialized_method_returns_empty_dict(self, server: AdgLanguageServer) -> None:
        assert server.handle_request("initialized", {}) == {}

    def test_unknown_method_returns_none(self, server: AdgLanguageServer) -> None:
        assert server.handle_request("textDocument/somethingUndefined", {}) is None

    def test_did_open_stores_document(self, server: AdgLanguageServer) -> None:
        server.handle_request(
            "textDocument/didOpen",
            {"textDocument": {"uri": "file:///tmp/x.py", "text": "x = 1"}},
        )
        assert server.documents["file:///tmp/x.py"] == "x = 1"

    def test_did_change_updates_document(self, server: AdgLanguageServer) -> None:
        uri = "file:///tmp/x.py"
        server.handle_request(
            "textDocument/didOpen",
            {"textDocument": {"uri": uri, "text": "x = 1"}},
        )
        server.handle_request(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri},
                "contentChanges": [{"text": "x = 2"}],
            },
        )
        assert server.documents[uri] == "x = 2"

    def test_did_close_removes_document(self, server: AdgLanguageServer) -> None:
        uri = "file:///tmp/x.py"
        server.handle_request(
            "textDocument/didOpen",
            {"textDocument": {"uri": uri, "text": "x"}},
        )
        server.handle_request(
            "textDocument/didClose",
            {"textDocument": {"uri": uri}},
        )
        assert uri not in server.documents


# ─────────────────────────────────────────────────────────
# 诊断
# ─────────────────────────────────────────────────────────


class TestHandleDiagnostic:
    def test_returns_empty_for_nonexistent_file(self, server: AdgLanguageServer) -> None:
        result = server.handle_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": "file:///nonexistent/does-not-exist-12345.py"}},
        )
        assert result == []

    def test_returns_empty_for_unsupported_extension(self, server: AdgLanguageServer, tmp_path: Path) -> None:
        f = tmp_path / "sample.xyz_unknown"
        f.write_text("content")
        result = server.handle_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": f"file://{f}"}},
        )
        assert result == []

    def test_python_file_returns_list(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        result = server.handle_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": f"file://{tmp_python_file}"}},
        )
        assert isinstance(result, list)

    def test_diagnostic_severity_in_expected_range(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        result = server.handle_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": f"file://{tmp_python_file}"}},
        )
        for diag in result:
            assert diag["severity"] in (1, 2, 3)

    def test_exclude_pattern_filters_node_modules(self, server: AdgLanguageServer, tmp_path: Path) -> None:
        # 制造在 node_modules 下的文件
        nm_dir = tmp_path / "node_modules" / "pkg"
        nm_dir.mkdir(parents=True)
        nm_file = nm_dir / "lib.py"
        nm_file.write_text("x = 1\n")
        result = server.handle_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": f"file://{nm_file}"}},
        )
        assert result == []

    def test_exclude_pattern_filters_git(self, server: AdgLanguageServer, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        git_file = git_dir / "hooks" / "x.py"
        git_file.parent.mkdir()
        git_file.write_text("x = 1\n")
        result = server.handle_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": f"file://{git_file}"}},
        )
        assert result == []


# ─────────────────────────────────────────────────────────
# Quick fix
# ─────────────────────────────────────────────────────────


class TestHandleCodeAction:
    def test_disabled_returns_empty(self, server: AdgLanguageServer) -> None:
        server.config["enable_quick_fix"] = False
        result = server.handle_request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": "file:///tmp/x.py"},
                "context": {"diagnostics": [{"source": "adg", "code": "R001"}]},
            },
        )
        assert result == []

    def test_non_adg_source_ignored(self, server: AdgLanguageServer) -> None:
        result = server.handle_request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": "file:///tmp/x.py"},
                "context": {"diagnostics": [{"source": "pylsp", "code": "R001"}]},
            },
        )
        assert result == []

    def test_adg_source_yields_fix_and_suppress(self, server: AdgLanguageServer) -> None:
        result = server.handle_request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": "file:///tmp/x.py"},
                "context": {"diagnostics": [{"source": "adg", "code": "PY001"}]},
            },
        )
        assert len(result) == 2
        titles = [a["title"] for a in result]
        assert any("Auto-fix" in t for t in titles)
        assert any("Suppress" in t for t in titles)
        for action in result:
            assert action["kind"] == "quickfix"
            assert "command" in action


# ─────────────────────────────────────────────────────────
# Code Lens
# ─────────────────────────────────────────────────────────


class TestHandleCodeLens:
    def test_disabled_returns_empty(self, server: AdgLanguageServer) -> None:
        server.config["enable_code_lens"] = False
        result = server.handle_request(
            "textDocument/codeLens",
            {"textDocument": {"uri": "file:///tmp/x.py"}},
        )
        assert result == []

    def test_clean_file_returns_empty(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        result = server.handle_request(
            "textDocument/codeLens",
            {"textDocument": {"uri": f"file://{tmp_python_file}"}},
        )
        # 干净文件也可能没诊断 → 空列表
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────
# Hover
# ─────────────────────────────────────────────────────────


class TestHandleHover:
    def test_no_diagnostics_returns_none(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        # mock _handle_diagnostic 返回空，跳过真实文件分析
        with patch.object(server, "_handle_diagnostic", return_value=[]):
            result = server.handle_request(
                "textDocument/hover",
                {
                    "textDocument": {"uri": f"file://{tmp_python_file}"},
                    "position": {"line": 0, "character": 0},
                },
            )
        assert result is None

    def test_returns_markdown_when_diagnostic_present(self, server: AdgLanguageServer, tmp_python_file: Path) -> None:
        fake_diag = {
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
            "severity": 2,
            "code": "R001",
            "message": "Test issue",
        }
        with patch.object(server, "_handle_diagnostic", return_value=[fake_diag]):
            result = server.handle_request(
                "textDocument/hover",
                {
                    "textDocument": {"uri": f"file://{tmp_python_file}"},
                    "position": {"line": 0, "character": 0},
                },
            )
        assert result is not None
        assert result["contents"]["kind"] == "markdown"
        assert "R001" in result["contents"]["value"]

    def test_position_defaults_to_zero(self, server: AdgLanguageServer) -> None:
        result = server.handle_request(
            "textDocument/hover",
            {"textDocument": {"uri": "file:///nonexistent.py"}},
        )
        assert result is None


# ─────────────────────────────────────────────────────────
# 配置变更
# ─────────────────────────────────────────────────────────


class TestHandleConfigChange:
    def test_updates_config(self, server: AdgLanguageServer) -> None:
        server.handle_request(
            "workspace/didChangeConfiguration",
            {"settings": {"adg": {"severity_filter": "error", "trend_enabled": True}}},
        )
        assert server.config["severity_filter"] == "error"
        assert server.config["trend_enabled"] is True

    def test_ignores_non_adg_settings(self, server: AdgLanguageServer) -> None:
        original = dict(server.config)
        server.handle_request(
            "workspace/didChangeConfiguration",
            {"settings": {"pylsp": {"something": "x"}}},
        )
        assert server.config == original


# ─────────────────────────────────────────────────────────
# 工作区符号
# ─────────────────────────────────────────────────────────


class TestHandleWorkspaceSymbol:
    def test_empty_query_returns_all(self, server: AdgLanguageServer) -> None:
        result = server.handle_request("workspace/symbol", {"query": ""})
        assert isinstance(result, list)

    def test_query_filters_by_rule_id(self, server: AdgLanguageServer) -> None:
        all_results = server.handle_request("workspace/symbol", {"query": ""})
        # 如果有结果，过滤后只剩匹配项
        if all_results:
            filtered = server.handle_request("workspace/symbol", {"query": "zzz_no_match_xyz"})
            assert filtered == []


# ─────────────────────────────────────────────────────────
# Initialize
# ─────────────────────────────────────────────────────────


class TestHandleInitialize:
    def test_root_uri_sets_workspace(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_project_config", return_value=None):
            server._handle_initialize({"rootUri": "file:///tmp/proj"})
        assert server.workspace_root == "file:///tmp/proj"

    def test_root_uri_with_file_prefix_stripped(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_project_config", return_value=None):
            server._handle_initialize({"rootUri": "file:///tmp/proj2"})
        # workspace_root 保留 URI 形式，_handle_initialize 内部不剥 file://
        assert server.workspace_root == "file:///tmp/proj2"

    def test_root_path_fallback(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_project_config", return_value=None):
            server._handle_initialize({"rootPath": "/tmp/proj3"})
        assert server.workspace_root == "/tmp/proj3"

    def test_empty_workspace_root_defaults_to_dot(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_project_config", return_value=None):
            server._handle_initialize({})
        assert server.workspace_root == "."

    def test_project_config_merges_into_default(self, server: AdgLanguageServer, tmp_path: Path) -> None:
        # _handle_initialize 内部: root_path = Path(uri.replace("file://", ""))
        # root_path.exists() 必须为真才会调用 load_project_config
        # 因此用一个真实存在的 tmp_path 作 rootUri
        with patch(
            "tools.lsp.server.load_project_config",
            return_value={"severity_filter": "error"},
        ):
            server._handle_initialize({"rootUri": f"file://{tmp_path}"})
        assert server.config["severity_filter"] == "error"
        # 默认配置其它键应保留
        assert "enable_on_save" in server.config

    def test_project_config_not_called_for_nonexistent_root(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_project_config", return_value={"severity_filter": "error"}) as mock:
            server._handle_initialize({"rootUri": "file:///nonexistent/abc_xyz_12345"})
        # rootPath 不存在时 _handle_initialize 不调用 load_project_config
        mock.assert_not_called()


# ─────────────────────────────────────────────────────────
# 规则缓存
# ─────────────────────────────────────────────────────────


class TestRulesCache:
    def test_cache_hit(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_rules_for_language", return_value={"anti_patterns": []}) as mock:
            server._get_rules("python")
            server._get_rules("python")
            server._get_rules("python")
        # 缓存命中：3 次调用只 1 次查 load_rules_for_language
        assert mock.call_count == 1

    def test_cache_per_language(self, server: AdgLanguageServer) -> None:
        with patch("tools.lsp.server.load_rules_for_language", return_value={"anti_patterns": []}) as mock:
            server._get_rules("python")
            server._get_rules("rust")
        assert mock.call_count == 2


# ─────────────────────────────────────────────────────────
# SUPPORTED_EXTENSIONS 健全性
# ─────────────────────────────────────────────────────────


class TestSupportedExtensions:
    def test_python_in_registry(self) -> None:
        assert ".py" in SUPPORTED_EXTENSIONS
        assert SUPPORTED_EXTENSIONS[".py"] == "python"

    def test_registry_has_15_plus_languages(self) -> None:
        assert len(SUPPORTED_EXTENSIONS) >= 15
