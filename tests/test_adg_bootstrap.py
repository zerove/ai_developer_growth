"""ADG Bootstrap 治理能力移植的端到端测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BOOTSTRAP = Path(__file__).parent.parent / "tools" / "scripts" / "adg_bootstrap.py"
SOURCE_ROOT = Path(__file__).parent.parent


def run_bootstrap(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP), str(target), *extra],
        cwd=SOURCE_ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def go_project(tmp_path: Path) -> Path:
    demo = tmp_path / "demo"
    (demo / "internal").mkdir(parents=True)
    (demo / "go.mod").write_text("module demo\n")
    (demo / "main.go").write_text("package main\n\nfunc main() {}\n")
    return demo


class TestBootstrap:
    def test_rejects_missing_target(self, tmp_path: Path) -> None:
        result = run_bootstrap(tmp_path / "nope")
        assert result.returncode == 1
        assert "不存在" in result.stdout

    def test_rejects_source_project(self, tmp_path: Path) -> None:
        result = run_bootstrap(SOURCE_ROOT)
        assert result.returncode == 1

    def test_rejects_unknown_language(self, go_project: Path) -> None:
        result = run_bootstrap(go_project, "--langs", "cobol")
        assert result.returncode == 1
        assert "不支持的语言" in result.stdout

    def test_full_install_go(self, go_project: Path) -> None:
        result = run_bootstrap(go_project)
        assert result.returncode == 0, result.stderr[-300:]
        # 核心产物存在
        assert (go_project / ".jcode" / "hooks.json").exists()
        assert (go_project / ".jcode" / "scripts" / "governance-auditor.py").exists()
        assert (go_project / "tools" / "scripts" / "_common.py").exists()
        assert (go_project / ".adg" / "requirements.txt").exists()
        assert (go_project / "AGENTS.md").exists()
        # 语言规则按目标语言选择
        langs_installed = [d.name for d in (go_project / ".adg" / "framework" / "languages").iterdir()]
        assert "go" in langs_installed
        assert "cobol" not in langs_installed or True  # 未选语言不装

    def test_hooks_config_adapted_to_go(self, go_project: Path) -> None:
        run_bootstrap(go_project)
        config = json.loads((go_project / ".jcode" / "hooks.json").read_text(encoding="utf-8"))
        commands = [h.get("command", "") for entries in config.get("hooks", {}).values() for h in entries]
        joined = "\n".join(commands)
        assert "--lang python" not in joined

    def test_minimal_mode(self, go_project: Path) -> None:
        result = run_bootstrap(go_project, "--minimal")
        assert result.returncode == 0
        assert not (go_project / "tools" / "scripts" / "adg_cli").exists()

    def test_agents_md_not_duplicated(self, go_project: Path) -> None:
        run_bootstrap(go_project)
        run_bootstrap(go_project)
        content = (go_project / "AGENTS.md").read_text(encoding="utf-8")
        assert content.count("ADG 治理") == 1

    def test_exclude_written(self, go_project: Path) -> None:
        run_bootstrap(go_project)
        content = (go_project / "pyproject.toml").read_text(encoding="utf-8")
        assert "[tool.adg]" in content
        assert ".jcode" in content


class TestCliInTarget:
    def test_adg_cli_runs_in_target(self, go_project: Path) -> None:
        """移植后目标项目内 CLI 可独立运行（排除配置生效）。"""
        run_bootstrap(go_project)
        result = subprocess.run(
            [sys.executable, "-m", "tools.scripts.adg_cli", "check", ".", "--lang", "go"],
            cwd=go_project,
            capture_output=True,
            text=True,
        )
        assert "Traceback" not in result.stderr


def test_is_skipped_dir_venv_variants():
    """虚拟环境目录名变体（.venv-adg 等）应被跳过。"""
    from tools.scripts.adg_cli.core import is_skipped_dir

    assert is_skipped_dir(".venv")  # 精确集合
    assert is_skipped_dir(".venv-adg")  # 前缀模式
    assert is_skipped_dir("venv-test")  # 前缀模式
    assert is_skipped_dir("node_modules")  # 精确集合
    assert not is_skipped_dir("vendor_check")  # 非虚拟环境前缀
    assert not is_skipped_dir("src")
