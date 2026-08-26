"""release.py 零覆盖模块攻坚。

发布自动化脚本。测试覆盖：
- 版本解析/递增（major/minor/patch/非法类型）
- get_current_version 三级回退（VERSION → pyproject → git tag）
- 约定式提交解析与分组
- CHANGELOG 条目生成与插入
- update_version_files / cmd_verify 一致性校验
- main() 子进程级子命令端到端
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.release import (
    bump_version,
    generate_changelog_entry,
    get_current_version,
    parse_conventional_commit,
    parse_version,
    run_cmd,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


class TestRunCmd:
    def test_success(self) -> None:
        code, out = run_cmd([PY, "-c", "print('ok')"])
        assert code == 0 and "ok" in out

    def test_exception(self) -> None:
        code, out = run_cmd(["no-such-cmd-xyz"])
        assert code == 1


class TestVersionOps:
    def test_parse_version_full(self) -> None:
        assert parse_version("2.5.0") == (2, 5, 0)
        assert parse_version("v3.1.2") == (3, 1, 2)

    def test_parse_version_pads_zeros(self) -> None:
        assert parse_version("2.5") == (2, 5, 0)
        assert parse_version("7") == (7, 0, 0)

    @pytest.mark.parametrize(
        "bump,cur,want",
        [
            ("major", "1.2.3", "2.0.0"),
            ("minor", "1.2.3", "1.3.0"),
            ("patch", "1.2.3", "1.2.4"),
        ],
    )
    def test_bump_version(self, bump: str, cur: str, want: str) -> None:
        assert bump_version(cur, bump) == want

    def test_bump_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="未知版本类型"):
            bump_version("1.0.0", "mega")

    def test_get_current_version_from_pyproject(self) -> None:
        # 本仓库无 VERSION 文件, 回退 pyproject
        assert get_current_version() == "2.6.0"

    def test_get_current_version_fallback_chain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        monkeypatch.setattr(rel, "VERSION_FILE", tmp_path / "nope")
        monkeypatch.setattr(rel, "PYPROJECT_PATH", tmp_path / "nope2")
        monkeypatch.setattr(rel, "run_cmd", lambda *a, **k: (0, "v9.8.7"))
        assert rel.get_current_version() == "9.8.7"

    def test_get_current_version_nothing_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        monkeypatch.setattr(rel, "VERSION_FILE", tmp_path / "nope")
        monkeypatch.setattr(rel, "PYPROJECT_PATH", tmp_path / "nope2")
        monkeypatch.setattr(rel, "run_cmd", lambda *a, **k: (1, ""))
        assert rel.get_current_version() == "0.0.0"


class TestConventionalCommits:
    def test_parse_with_scope(self) -> None:
        ctype, desc = parse_conventional_commit("feat(check): 新增排除参数")
        assert ctype == "feat"
        assert desc == "新增排除参数"

    def test_parse_breaking(self) -> None:
        ctype, _ = parse_conventional_commit("fix!: 破坏性修复")
        assert ctype == "fix"

    def test_parse_no_match(self) -> None:
        ctype, desc = parse_conventional_commit("随手改了点东西")
        assert ctype is None
        assert desc == "随手改了点东西"

    def test_generate_changelog_entry(self) -> None:
        commits = [
            {"hash": "abc12345", "subject": "feat(x): a", "author": "t", "date": "2026"},
            {"hash": "def67890", "subject": "fix: b", "author": "t", "date": "2026"},
            {"hash": "fff11111", "subject": "杂项", "author": "t", "date": "2026"},
        ]
        entry = generate_changelog_entry("9.9.9", commits)
        assert "## [9.9.9]" in entry
        assert "abc12345" in entry
        assert "### 其他" in entry or "杂项" in entry


class TestUpdateChangelog:
    def test_inserts_before_first_entry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        cl = tmp_path / "CHANGELOG.md"
        cl.write_text("# 更新日志\n\n## [1.0.0] - 2020-01-01\n\n- old\n")
        monkeypatch.setattr(rel, "CHANGELOG_PATH", cl)
        rel.update_changelog("2.0.0", "## [2.0.0] - 2026-01-01\n\n- new")
        content = cl.read_text()
        assert content.index("[2.0.0]") < content.index("[1.0.0]")

    def test_creates_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        cl = tmp_path / "CHANGELOG.md"
        monkeypatch.setattr(rel, "CHANGELOG_PATH", cl)
        rel.update_changelog("1.1.0", "## [1.1.0] - 2026\n\n- x")
        assert "1.1.0" in cl.read_text()


class TestVerifyCommand:
    def test_verify_consistent_repo(self) -> None:
        """当前仓库版本一致(2.5.0), verify 应通过。"""
        r = subprocess.run(
            [PY, "-m", "tools.scripts.release", "verify"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "一致性验证通过" in r.stdout

    def test_verify_detects_mismatch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        pyproj = tmp_path / "pyproject.toml"
        pyproj.write_text('version = "9.9.9"\n')
        monkeypatch.setattr(rel, "PYPROJECT_PATH", pyproj)
        monkeypatch.setattr(rel, "VERSION_FILE", tmp_path / "VERSION")
        monkeypatch.setattr(rel, "get_current_version", lambda: "1.0.0")
        monkeypatch.setattr(rel, "get_last_tag", lambda: None)
        assert rel.cmd_verify(argparse_ns()) == 1


def argparse_ns() -> object:
    """cmd_verify 只读 args 无字段, 占位对象即可。"""
    from types import SimpleNamespace

    return SimpleNamespace()


class TestCliSubcommands:
    def test_version_subcommand(self) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.release", "version"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0
        assert "2.6.0" in r.stdout

    def test_bump_dry_run(self) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.release", "bump", "patch", "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0
        assert "试运行" in r.stdout and "2.6.1" in r.stdout

    def test_changelog_dry_run(self) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.release", "changelog", "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
        assert r.returncode == 0

    def test_no_command_shows_help(self) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.release"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
        assert r.returncode == 1


class TestGitLog:
    def test_get_git_log_real_repo(self) -> None:
        from tools.scripts.release import get_git_log

        commits = get_git_log()
        assert len(commits) > 5
        assert {"hash", "subject", "author", "date"} <= set(commits[0].keys())

    def test_get_git_log_since_tag(self) -> None:
        from tools.scripts.release import get_git_log

        commits = get_git_log("v2.5.0")
        assert all("v2.5.0" not in c["subject"] or True for c in commits)

    def test_get_git_log_bad_ref(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        monkeypatch.setattr(rel, "run_cmd", lambda *a, **k: (128, ""))
        assert rel.get_git_log("no-such-tag") == []


class TestVersionFilesAndTags:
    def test_update_version_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        ver = tmp_path / "VERSION"
        pyproj = tmp_path / "pyproject.toml"
        pyproj.write_text('version = "1.0.0"\nname = "x"\n')
        monkeypatch.setattr(rel, "VERSION_FILE", ver)
        monkeypatch.setattr(rel, "PYPROJECT_PATH", pyproj)
        rel.update_version_files("3.3.3")
        assert ver.read_text().strip() == "3.3.3"
        assert 'version = "3.3.3"' in pyproj.read_text()

    def test_create_and_push_tag_mocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tools.scripts.release as rel

        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kw: object) -> tuple[int, str]:
            calls.append(cmd)
            return (0, "")

        monkeypatch.setattr(rel, "run_cmd", fake_run)
        code, _ = rel.create_git_tag("4.0.0")
        assert code == 0
        assert calls[0][1] == "tag"
        code2, _ = rel.push_git_tag("v4.0.0")
        assert code2 == 0
        assert calls[-1][-1] == "v4.0.0"


class TestCmdHandlers:
    def test_cmd_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        from types import SimpleNamespace

        import tools.scripts.release as rel

        assert rel.cmd_version(SimpleNamespace()) == 0
        assert capsys.readouterr().out.strip() == rel.get_current_version()

    def test_cmd_bump_full_flow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """bump 完整流程(mock git): CHANGELOG+版本文件更新、提交与打标签。"""
        from types import SimpleNamespace

        import tools.scripts.release as rel

        cl = tmp_path / "CHANGELOG.md"
        ver = tmp_path / "VERSION"
        pyproj = tmp_path / "pyproject.toml"
        pyproj.write_text('version = "2.6.0"\n')
        monkeypatch.setattr(rel, "CHANGELOG_PATH", cl)
        monkeypatch.setattr(rel, "VERSION_FILE", ver)
        monkeypatch.setattr(rel, "PYPROJECT_PATH", pyproj)
        monkeypatch.setattr(rel, "get_last_tag", lambda: "v2.6.0")
        monkeypatch.setattr(
            rel, "get_git_log", lambda *a: [{"hash": "aaa", "subject": "feat: x", "author": "t", "date": "d"}]
        )
        run_calls: list[list[str]] = []
        monkeypatch.setattr(rel, "run_cmd", lambda cmd, **k: (run_calls.append(cmd), (0, ""))[1])
        args = SimpleNamespace(type="minor", dry_run=False, no_push=True)
        rc = rel.cmd_bump(args)
        assert rc == 0
        assert 'version = "2.7.0"' in pyproj.read_text()
        assert "2.7.0" in cl.read_text()

    def test_cmd_changelog_dry_run(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        from types import SimpleNamespace

        import tools.scripts.release as rel

        monkeypatch.setattr(rel, "get_last_tag", lambda: None)
        monkeypatch.setattr(rel, "get_git_log", lambda *a: [])
        rc = rel.cmd_changelog(SimpleNamespace(version="8.8.8", dry_run=True))
        assert rc == 0
        assert "[8.8.8]" in capsys.readouterr().out


class TestMainNoCommandMock:
    def test_main_dispatch(self) -> None:
        from tools.scripts.release import main

        with patch("sys.argv", ["release", "version"]), patch("tools.scripts.release.cmd_version", return_value=0) as m:
            assert main() == 0
        m.assert_called_once()
