"""测试 scripts/install-governance.py（此前零测试、且不在任何门禁引用内）。

该脚本会写用户主目录（~/.jcode/governance）、复制 ai-dev-framework 整棵树，
属破坏性最强的未测脚本之一。

本轮补测时发现并修复的真实缺陷（见 TestMainPropagatesFailures）：
main() 的默认分支（无参数）无条件 `return 0`，丢弃 install_global() 与
init_project() 的返回值；而同一函数的 --path / --global-only 两个分支都
正确传递了。安装失败时脚本仍以成功退出，调用方会误判。

隔离要求：JCODE_GOVERNANCE 必须重定向到 tmp_path —— 该脚本默认写真实主目录。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def ig(tmp_path: Path):
    """加载脚本并把所有写盘目标重定向到 tmp_path。"""
    spec = importlib.util.spec_from_file_location("install_governance", ROOT / "scripts" / "install-governance.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 关键隔离：默认会写真实 ~/.jcode/governance
    mod.JCODE_GOVERNANCE = tmp_path / ".jcode" / "governance"
    return mod


def _run_main(ig, *argv: str) -> int:
    with patch.object(sys, "argv", ["install-governance.py", *argv]):
        return ig.main()


# ── main() 返回码（回归防护） ───────────────────────────────────────


class TestMainPropagatesFailures:
    def test_default_path_failure_exits_nonzero(self, ig) -> None:
        """回归防护：早前默认分支无条件 return 0，安装失败也报成功。"""
        with (
            patch.object(ig, "install_global", return_value=False),
            patch.object(ig, "init_project", return_value=True),
        ):
            assert _run_main(ig) == 1

    def test_default_path_project_failure_exits_nonzero(self, ig) -> None:
        with (
            patch.object(ig, "install_global", return_value=True),
            patch.object(ig, "init_project", return_value=False),
        ):
            assert _run_main(ig) == 1

    def test_default_path_both_ok_exits_zero(self, ig) -> None:
        with patch.object(ig, "install_global", return_value=True), patch.object(ig, "init_project", return_value=True):
            assert _run_main(ig) == 0

    def test_path_flag_propagates(self, ig) -> None:
        with patch.object(ig, "init_project", return_value=False):
            assert _run_main(ig, "--path", "somewhere") == 1

    def test_global_only_flag_propagates(self, ig) -> None:
        with patch.object(ig, "install_global", return_value=False):
            assert _run_main(ig, "--global-only") == 1

    def test_default_path_runs_both(self, ig) -> None:
        with (
            patch.object(ig, "install_global", return_value=True) as g,
            patch.object(ig, "init_project", return_value=True) as p,
        ):
            _run_main(ig)
        g.assert_called_once()
        p.assert_called_once()

    def test_path_flag_skips_global_install(self, ig) -> None:
        with patch.object(ig, "install_global") as g, patch.object(ig, "init_project", return_value=True):
            _run_main(ig, "--path", "somewhere")
        g.assert_not_called()

    def test_global_only_flag_skips_project_init(self, ig) -> None:
        with patch.object(ig, "install_global", return_value=True), patch.object(ig, "init_project") as p:
            _run_main(ig, "--global-only")
        p.assert_not_called()


# ── install_global ──────────────────────────────────────────────────


class TestInstallGlobal:
    def test_copies_framework_and_writes_files(self, ig) -> None:
        assert ig.install_global() is True
        base = ig.JCODE_GOVERNANCE
        assert (base / "ai-dev-framework").is_dir()
        assert (base / "adg").is_file()
        assert (base / "mode_decision.conf").is_file()

    def test_adg_wrapper_is_executable(self, ig) -> None:
        ig.install_global()
        import os

        assert os.access(ig.JCODE_GOVERNANCE / "adg", os.X_OK), "adg 包装脚本应可执行"

    def test_mode_conf_content(self, ig) -> None:
        ig.install_global()
        text = (ig.JCODE_GOVERNANCE / "mode_decision.conf").read_text(encoding="utf-8")
        assert "mode=quality" in text

    def test_reinstall_replaces_existing_tree(self, ig) -> None:
        """重装是净替换：自带旧文件应被清除。"""
        ig.install_global()
        stale = ig.JCODE_GOVERNANCE / "ai-dev-framework" / "STALE.txt"
        stale.write_text("x", encoding="utf-8")
        ig.install_global()
        assert not stale.exists(), "重装未清除旧内容"

    def test_pycache_excluded(self, ig) -> None:
        ig.install_global()
        assert not list((ig.JCODE_GOVERNANCE / "ai-dev-framework").rglob("__pycache__"))

    def test_nothing_written_to_real_home(self, ig) -> None:
        """隔离自检：真实主目录不应被创建。"""
        ig.install_global()
        assert ig.JCODE_GOVERNANCE != Path.home() / ".jcode" / "governance"


# ── init_project ────────────────────────────────────────────────────


class TestInitProject:
    def test_creates_jcode_dir(self, ig, tmp_path: Path) -> None:
        workdir = tmp_path / "proj"
        workdir.mkdir()
        with patch.object(ig, "PROJECT_ROOT", workdir), patch.object(ig, "THIS_DIR", workdir / "scripts"):
            ig.init_project()
        assert (workdir / ".jcode").is_dir()

    def test_does_not_clobber_existing_hooks_json(self, ig, tmp_path: Path) -> None:
        """已存在的 hooks.json 必须保留（早前有 if not exists 保护）。"""
        workdir = tmp_path / "proj2"
        (workdir / ".jcode").mkdir(parents=True)
        (workdir / ".jcode" / "hooks.json").write_text('{"mine": true}', encoding="utf-8")
        with patch.object(ig, "PROJECT_ROOT", workdir), patch.object(ig, "THIS_DIR", workdir / "scripts"):
            ig.init_project()
        assert (workdir / ".jcode" / "hooks.json").read_text(encoding="utf-8") == '{"mine": true}'

    def test_does_not_clobber_existing_pre_commit(self, ig, tmp_path: Path) -> None:
        workdir = tmp_path / "proj3"
        (workdir / ".jcode").mkdir(parents=True)
        pc = workdir / ".pre-commit-config.yaml"
        pc.write_text("mine: true\n", encoding="utf-8")
        with patch.object(ig, "PROJECT_ROOT", workdir), patch.object(ig, "THIS_DIR", workdir / "scripts"):
            ig.init_project()
        assert pc.read_text(encoding="utf-8") == "mine: true\n"

    def test_creates_missing_files(self, ig, tmp_path: Path) -> None:
        workdir = tmp_path / "proj4"
        workdir.mkdir()
        with patch.object(ig, "PROJECT_ROOT", workdir), patch.object(ig, "THIS_DIR", workdir / "scripts"):
            ig.init_project()
        assert (workdir / ".jcode" / "hooks.json").is_file()
        assert (workdir / ".pre-commit-config.yaml").is_file()
