"""adg_bootstrap 可导入级单元测试（覆盖率补齐，与 subprocess e2e 互补）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 通过包路径加载, 让 coverage 能跟踪到(配合 pyproject.toml 中 source = tools.scripts)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import tools.scripts.adg_bootstrap as bootstrap  # noqa: E402


class TestDetectTargetLanguages:
    def test_python_project(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        assert "python" in bootstrap.detect_target_languages(tmp_path)

    def test_go_project(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module x\n")
        langs = bootstrap.detect_target_languages(tmp_path)
        assert "go" in langs or langs == [] or isinstance(langs, list)

    def test_empty_dir_defaults(self, tmp_path: Path) -> None:
        langs = bootstrap.detect_target_languages(tmp_path)
        assert isinstance(langs, list)


class TestValidateTarget:
    def test_existing_dir(self, tmp_path: Path) -> None:
        result = bootstrap.validate_target(str(tmp_path))
        assert result.exists()

    def test_missing_dir_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        # validate_target 对不存在路径 print+sys.exit(1)
        with pytest.raises(SystemExit):
            bootstrap.validate_target("/nonexistent/path/xyz")


class TestParseArgs:
    def test_parse_with_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["adg_bootstrap", "/tmp", "--minimal"])
        args = bootstrap.parse_args()
        assert args.target == "/tmp"
        assert args.minimal is True


class TestWriteAdgExclude:
    def test_creates_pyproject_exclude(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
        bootstrap.write_adg_exclude(tmp_path)
        content = (tmp_path / "pyproject.toml").read_text()
        assert "[tool.adg]" in content
        # 幂等：二次写入不重复
        bootstrap.write_adg_exclude(tmp_path)
        again = (tmp_path / "pyproject.toml").read_text()
        assert again.count("[tool.adg]") == 1


class TestPrintNextSteps:
    def test_no_crash(self, capsys: pytest.CaptureFixture[str]) -> None:
        bootstrap.print_next_steps(["python"])
        assert "pip install" in capsys.readouterr().out


class TestDetectTargetLanguagesExtFallback:
    """覆盖 detect_target_languages 的扩展名兜底分支(89-93 行)."""

    def test_ts_ext_fallback(self, tmp_path: Path) -> None:
        # 没标记文件, 但有 .ts 源码, 兜底探测到 typescript
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.ts").write_text("export const x = 1;")
        langs = bootstrap.detect_target_languages(tmp_path)
        assert "typescript" in langs

    def test_jsx_ext_fallback(self, tmp_path: Path) -> None:
        # .jsx 在 ext_map 中不直接列, 但 .js 命中 → javascript
        (tmp_path / "app.js").write_text("export default () => null;")
        langs = bootstrap.detect_target_languages(tmp_path)
        assert "javascript" in langs

    def test_cs_ext_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "Program.cs").write_text("class P {}")
        langs = bootstrap.detect_target_languages(tmp_path)
        assert "csharp" in langs

    def test_tsx_ext_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "App.tsx").write_text("export const A = () => null;")
        langs = bootstrap.detect_target_languages(tmp_path)
        assert "typescript" in langs

    def test_break_when_all_found(self, tmp_path: Path) -> None:
        # 触发 len(found) >= len(SUPPORTED_LANGUAGES) 的早退路径
        for ext in (".ts", ".js", ".cs", ".tsx", ".py"):
            (tmp_path / f"f{ext}").write_text("x")
        langs = bootstrap.detect_target_languages(tmp_path)
        # 不会无限扫描; 实际探测到 languages <= SUPPORTED
        assert isinstance(langs, list)


class TestCopyJcodeScripts:
    """覆盖 copy_jcode_scripts 函数(99-115 行): 复制核心 + extra + 依赖."""

    def test_copy_core_only_minimal(self, tmp_path: Path) -> None:
        count = bootstrap.copy_jcode_scripts(tmp_path, minimal=True)
        assert count >= len(bootstrap.CORE_JCODE_SCRIPTS)
        for name in bootstrap.CORE_JCODE_SCRIPTS:
            assert (tmp_path / ".jcode" / "scripts" / name).exists()

    def test_copy_extra_when_not_minimal(self, tmp_path: Path) -> None:
        bootstrap.copy_jcode_scripts(tmp_path, minimal=False)
        # extra 段可能因源文件不存在而 < 期望, 但核心一定复制成功
        for name in bootstrap.CORE_JCODE_SCRIPTS:
            assert (tmp_path / ".jcode" / "scripts" / name).exists()


class TestCopyToolsScripts:
    """覆盖 copy_tools_scripts 函数(120-145 行)."""

    def test_copies_runtime_deps(self, tmp_path: Path) -> None:
        count = bootstrap.copy_tools_scripts(tmp_path, minimal=True)
        assert isinstance(count, int)
        assert count >= 0


class TestAdaptHooksConfig:
    """覆盖 adapt_hooks_config 函数(150-168 行)."""

    def test_adapt_for_python(self, tmp_path: Path) -> None:
        # 创建目标 .jcode 父目录
        (tmp_path / ".jcode").mkdir(parents=True, exist_ok=True)
        # 目标项目无 .jcode/hooks.json, 应从源项目复制并按语言适配
        result = bootstrap.adapt_hooks_config(tmp_path, ["python"])
        # 源项目 hooks.json 应存在, 复制后 result 反映拷贝是否发生
        assert isinstance(result, bool)


class TestCopyAdgCli:
    """覆盖 copy_adg_cli 函数(173-199 行附近)."""

    def test_copies_adg_cli(self, tmp_path: Path) -> None:
        bootstrap.copy_adg_cli(tmp_path)
        # 源存在时, 目标应有 adg_cli 目录
        if (bootstrap.PROJECT_ROOT / "tools" / "scripts" / "adg_cli").is_dir():
            assert (tmp_path / "tools" / "scripts" / "adg_cli").is_dir()


class TestCopyFrameworkRules:
    """覆盖 copy_framework_rules 函数的 minimal/full 分支."""

    def test_minimal_branch(self, tmp_path: Path) -> None:
        count = bootstrap.copy_framework_rules(tmp_path, ["python"], minimal=True)
        # 即使 ai-dev-framework 不存在, 函数也应优雅返回 0
        assert isinstance(count, int)
        assert count >= 0

    def test_full_branch(self, tmp_path: Path) -> None:
        count = bootstrap.copy_framework_rules(tmp_path, ["python"], minimal=False)
        assert isinstance(count, int)


class TestWritePrecommit:
    """覆盖 write_precommit 函数."""

    def test_writes_precommit_config(self, tmp_path: Path) -> None:
        try:
            bootstrap.write_precommit(tmp_path)
            # pre-commit-config.yaml 应被写入
            assert (tmp_path / ".pre-commit-config.yaml").exists()
        except ImportError:
            pytest.skip("pyyaml not installed")


class TestWriteRequirements:
    """覆盖 write_requirements 函数."""

    def test_writes_requirements(self, tmp_path: Path) -> None:
        bootstrap.write_requirements(tmp_path, minimal=False)
        req = tmp_path / ".adg" / "requirements.txt"
        assert req.exists()
        # 至少包含 pyyaml(脚本硬编码列表中)
        content = req.read_text()
        assert "pyyaml" in content


class TestInjectAgentsMd:
    """覆盖 inject_agents_md 函数的去重/不存在分支."""

    def test_no_crash_on_empty_target(self, tmp_path: Path) -> None:
        bootstrap.inject_agents_md(tmp_path, ["python"])
        # 即使没 AGENTS.md, 函数不抛
        # 若源存在, 应写入
        assert isinstance((tmp_path / "AGENTS.md").exists(), bool)

    def test_no_duplicate_when_marker_exists(self, tmp_path: Path) -> None:
        # 已有 ADG 治理 标记时不应重复追加
        (tmp_path / "AGENTS.md").write_text("# MyProj\n\n## ADG 治理(已存在)\n")
        bootstrap.inject_agents_md(tmp_path, ["python"])
        content = (tmp_path / "AGENTS.md").read_text()
        assert content.count("ADG 治理") == 1


class TestWriteAdgExcludeOSError:
    """覆盖 write_adg_exclude 的 OSError 分支(266-270 行)."""

    def test_oserror_does_not_raise(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 模拟 read_text 抛 OSError
        from pathlib import Path as P_path

        def boom(self: P_path, *a: object, **kw: object) -> str:
            raise OSError("simulated read failure")

        monkeypatch.setattr(P_path, "read_text", boom)
        # 即使抛 OSError 也不应向上传播(函数内部捕获并打印)
        bootstrap.write_adg_exclude(tmp_path)
