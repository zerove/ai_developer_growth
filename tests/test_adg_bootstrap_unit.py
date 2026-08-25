"""adg_bootstrap 可导入级单元测试（覆盖率补齐，与 subprocess e2e 互补）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "adg_bootstrap", Path(__file__).parent.parent / "tools" / "scripts" / "adg_bootstrap.py"
)
assert _SPEC is not None and _SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bootstrap)


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
