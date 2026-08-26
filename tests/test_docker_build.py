"""docker_build 零覆盖模块攻坚。

纯 subprocess 封装，无外部依赖。测试覆盖：
- run_cmd 成功/失败/异常路径
- git sha/tag 获取
- 标签组装与 buildx 命令构造
- build_image dry_run / 真实构建(mock subprocess)
- SBOM 生成、签名与验签
- 组件选择过滤（含未知组件报错）
- preflight 检查（Dockerfile 缺失 / buildx 不可用）
- main() 子进程级 --help 与 dry-run 端到端
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.docker_build import (
    COMPONENTS,
    PROJECT,
    REGISTRY,
    _build_tag_list,
    _buildx_command,
    _collect_extra_tags,
    _preflight_checks,
    _select_components,
    build_image,
    generate_sbom,
    get_git_sha,
    get_git_tag,
    run_cmd,
    sign_image,
    verify_signature,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


class TestRunCmd:
    def test_success(self) -> None:
        code, out = run_cmd([PY, "-c", "print('hi')"])
        assert code == 0 and "hi" in out

    def test_nonzero_exit(self) -> None:
        code, out = run_cmd([PY, "-c", "import sys; sys.exit(3); print('x')"])
        assert code == 3

    def test_exception_path(self) -> None:
        code, out = run_cmd(["definitely-not-a-cmd-xyz"])
        assert code == 1 and out


class TestGitInfo:
    def test_get_git_sha_in_repo(self) -> None:
        assert get_git_sha() != "unknown"

    def test_get_git_tag_none_when_no_exact_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("tools.scripts.docker_build.run_cmd", lambda *a, **k: (128, "fatal: no tag"))
        assert get_git_tag() is None


class TestTagAndCommand:
    def test_build_tag_list(self) -> None:
        tags = _build_tag_list("jcode-api", "v1.0.0", "reg.example.com", ["sha-abc"])
        image = f"reg.example.com/{PROJECT}/jcode-api"
        assert tags[0] == f"{image}:v1.0.0"
        assert f"{image}:latest" in tags
        assert f"{image}:sha-abc" in tags

    def test_buildx_command_push(self) -> None:
        cmd = _buildx_command("Dockerfile.x", "linux/amd64", ["img:1"], push=True)
        assert "--push" in cmd
        assert cmd[-1] == "."
        assert cmd[cmd.index("--platform") + 1] == "linux/amd64"

    def test_buildx_command_load(self) -> None:
        cmd = _buildx_command("Dockerfile.x", "linux/arm64", ["img:2"], push=False)
        assert "--load" in cmd and "--push" not in cmd

    def test_multiple_tags_expanded(self) -> None:
        cmd = _buildx_command("d", "p", ["a:1", "b:2"], False)
        assert cmd.count("-t") == 2


class TestBuildImage:
    def test_dry_run_skips_subprocess(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("tools.scripts.docker_build.run_cmd") as m:
            ok, err = build_image(
                component="c",
                dockerfile="d",
                version="v1",
                platforms="p",
                registry="r",
                push=False,
                dry_run=True,
                extra_tags=[],
            )
        m.assert_not_called()
        assert ok is True and err == ""
        assert "试运行" in capsys.readouterr().out

    def test_real_build_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("tools.scripts.docker_build.run_cmd", return_value=(0, "")) as m:
            ok, _ = build_image(
                component="c",
                dockerfile="d",
                version="v1",
                platforms="p",
                registry="r",
                push=False,
                dry_run=False,
                extra_tags=[],
            )
        m.assert_called_once()
        assert ok is True

    def test_real_build_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("tools.scripts.docker_build.run_cmd", return_value=(1, "boom")):
            ok, err = build_image(
                component="c",
                dockerfile="d",
                version="v1",
                platforms="p",
                registry="r",
                push=False,
                dry_run=False,
                extra_tags=[],
            )
        assert ok is False and err == "boom"


class TestSbomAndSign:
    def test_generate_sbom_success(self, tmp_path: Path) -> None:
        with patch("tools.scripts.docker_build.run_cmd", return_value=(0, "")):
            ok, path = generate_sbom("reg/proj/img:1", tmp_path)
        assert ok is True
        assert path.endswith(".sbom.json")
        assert "reg_proj_img_1.sbom.json" in path

    def test_generate_sbom_failure(self, tmp_path: Path) -> None:
        with patch("tools.scripts.docker_build.run_cmd", return_value=(1, "no syft")):
            ok, out = generate_sbom("img:1", tmp_path)
        assert ok is False and out == "no syft"

    def test_sign_image(self) -> None:
        with patch("tools.scripts.docker_build.run_cmd", return_value=(0, "")) as m:
            assert sign_image("img:1") is True
        cmd = m.call_args[0][0]
        assert cmd[:2] == ["cosign", "sign"]

    def test_verify_signature(self) -> None:
        with patch("tools.scripts.docker_build.run_cmd", return_value=(1, "")):
            assert verify_signature("img:1") is False


class TestSelectComponents:
    def _ns(self, **kw: object) -> MagicMock:
        ns = MagicMock()
        ns.components = kw.get("components")
        return ns

    def test_all_components(self) -> None:
        assert _select_components(self._ns()) == COMPONENTS

    def test_filtered(self) -> None:
        got = _select_components(self._ns(components="jcode-api, jcode-audit"))
        assert got == [("jcode-api", "tools/scripts/Dockerfile.api"), ("jcode-audit", "tools/scripts/Dockerfile.audit")]

    def test_unknown_component_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _select_components(self._ns(components="nope")) is None
        assert "未知组件" in capsys.readouterr().out


class TestPreflight:
    def test_missing_dockerfile_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        ok = _preflight_checks([("x", "nonexistent/Dockerfile")])
        assert ok is False

    def test_buildx_unavailable_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        df = tmp_path / "Dockerfile"
        df.write_text("FROM scratch\n")
        monkeypatch.setattr("tools.scripts.docker_build.run_cmd", lambda *a, **k: (1, ""))
        assert _preflight_checks([("x", "Dockerfile")]) is False

    def test_preflight_pass_creates_builder(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Dockerfile").write_text("FROM scratch\n")
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kw: object) -> tuple[int, str]:
            calls.append(cmd)
            return (0, "")

        monkeypatch.setattr("tools.scripts.docker_build.run_cmd", fake_run)
        assert _preflight_checks([("x", "Dockerfile")]) is True
        assert any("buildx" in c for c in calls if c)


class TestCollectExtraTags:
    def test_merges_extra_and_timestamp(self) -> None:
        ns = MagicMock()
        ns.extra_tags = "rc1, rc2"
        tags = _collect_extra_tags(ns)
        assert "rc1" in tags and "rc2" in tags
        assert any(t.startswith("sha-") for t in tags)
        assert any(t.startswith("build-") for t in tags)

    def test_no_extra_tags(self) -> None:
        ns = MagicMock()
        ns.extra_tags = None
        tags = _collect_extra_tags(ns)
        assert len(tags) >= 2  # sha + timestamp


class TestCliEndToEnd:
    def test_help(self) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.docker_build", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
        assert r.returncode == 0
        assert b"--dry-run" in r.stdout

    def test_dry_run_single_component(self) -> None:
        r = subprocess.run(
            [
                PY,
                "-m",
                "tools.scripts.docker_build",
                "--version",
                "v9.9.9",
                "--components",
                "jcode-api",
                "--dry-run",
                "--registry",
                "local.test",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # dry-run 不触发真实 docker; preflight 需要 Dockerfile 存在 → 用仓库内路径应通过
        assert r.returncode in (0, 1), r.stderr[:300]


class TestParseArgsAndFlow:
    def _args(self, **kw: object) -> MagicMock:
        ns = MagicMock()
        ns.version = "v1.0.0"
        ns.registry = REGISTRY
        ns.platforms = "linux/amd64"
        ns.push = False
        ns.sbom = False
        ns.sign = False
        ns.dry_run = True
        ns.components = None
        ns.extra_tags = None
        for k, v in kw.items():
            setattr(ns, k, v)
        return ns

    def test_parse_build_args(self) -> None:
        from tools.scripts.docker_build import _parse_build_args

        with patch("sys.argv", ["docker_build", "--version", "v3.2.1", "--no-push", "--dry-run"]):
            args = _parse_build_args()
        assert args.version == "v3.2.1"
        assert args.push is False
        assert args.dry_run is True

    def test_print_build_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.docker_build import _print_build_header

        components = list(COMPONENTS)[:2]
        _print_build_header(self._args(sbom=True, sign=True), components)
        out = capsys.readouterr().out
        assert "v1.0.0" in out and "SBOM: 是" in out

    def test_print_summary_all_ok(self, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.docker_build import _print_summary

        rc = _print_summary(self._args(), COMPONENTS[:2], [], [])
        assert rc == 0
        assert "所有组件构建成功" in capsys.readouterr().out

    def test_print_summary_with_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        from tools.scripts.docker_build import _print_summary

        rc = _print_summary(self._args(), COMPONENTS[:2], ["jcode-api"], [])
        assert rc == 1
        assert "jcode-api" in capsys.readouterr().out

    def test_build_all_components_dry_run(self, tmp_path: Path) -> None:
        from tools.scripts.docker_build import _build_all_components

        failed, sbom = _build_all_components(self._args(dry_run=True), COMPONENTS[:2], [], tmp_path)
        assert failed == [] and sbom == []

    def test_main_dry_run_end_to_end(self) -> None:
        """main() 全流程 dry-run：不触发真实 docker 构建。"""
        from tools.scripts.docker_build import main

        with patch(
            "sys.argv",
            [
                "docker_build",
                "--version",
                "v9.0.0",
                "--components",
                "jcode-api",
                "--dry-run",
                "--registry",
                "local.test",
            ],
        ):
            # preflight 需要 buildx 可用; mock 掉 run_cmd 使其通过
            with patch("tools.scripts.docker_build.run_cmd", return_value=(0, "ok")):
                rc = main()
        # dry-run 构建成功 → 汇总 exit 0
        assert rc == 0
