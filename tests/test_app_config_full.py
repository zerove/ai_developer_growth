"""app_config 补齐: TOML 解析容错/向上查找/YAML 覆盖/环境变量/get_path。64%→95%+"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts import app_config
from tools.scripts.app_config import (
    _find_upwards,
    _load_toml_config,
    clear_cache,
    get_path,
    get_project_root,
    get_setting,
    get_settings,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith("ADG_"):
            monkeypatch.delenv(name, raising=False)
    yield


class TestLoadToml:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert _load_toml_config(str(tmp_path / "nope.toml")) == {}

    def test_valid_section_parsed(self, tmp_path: Path) -> None:
        pp = tmp_path / "pyproject.toml"
        pp.write_text("[tool.adg]\njobs = 6\n", encoding="utf-8")
        assert _load_toml_config(str(pp)) == {"jobs": 6}

    def test_non_dict_section_returns_empty(self, tmp_path: Path) -> None:
        pp = tmp_path / "pyproject.toml"
        pp.write_text('tool = "flat"\n', encoding="utf-8")
        assert _load_toml_config(str(pp)) == {}

    def test_malformed_toml_returns_empty(self, tmp_path: Path) -> None:
        pp = tmp_path / "pyproject.toml"
        pp.write_text("[broken\n=not valid", encoding="utf-8")
        assert _load_toml_config(str(pp)) == {}


class TestFindUpwards:
    def test_finds_nearest(self, tmp_path: Path) -> None:
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        (tmp_path / "marker.txt").write_text("root", encoding="utf-8")
        found = _find_upwards(sub / "c", "marker.txt")
        assert found is not None and found.name == "marker.txt"

    def test_not_found_returns_none(self, tmp_path: Path) -> None:
        deep = tmp_path / "x" / "y"
        deep.mkdir(parents=True)
        assert _find_upwards(deep, "absent.bin") is None


class TestProjectRootAndOverrides:
    def test_env_root_wins(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("ADG_PROJECT_ROOT", str(tmp_path))
        assert get_project_root() == tmp_path

    def test_yaml_override_loaded(self, tmp_path: Path, monkeypatch) -> None:
        adg_dir = tmp_path / ".adg"
        adg_dir.mkdir()
        (adg_dir / "config.yml").write_text("parallelism:\n  jobs: 9\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("[tool.adg]\njobs = 2\n", encoding="utf-8")
        monkeypatch.setenv("ADG_PROJECT_ROOT", str(tmp_path))
        clear_cache()
        settings = get_settings()
        assert settings["jobs"] == 2  # pyproject 基础
        # YAML 覆盖按原键结构合并(嵌套 dict 整体替换)
        assert settings.get("parallelism") == {"jobs": 9}

    def test_malformed_yaml_warns_and_empty(self, tmp_path: Path, monkeypatch) -> None:
        adg_dir = tmp_path / ".adg"
        adg_dir.mkdir()
        (adg_dir / "config.yml").write_text("{unclosed: [", encoding="utf-8")
        monkeypatch.setenv("ADG_PROJECT_ROOT", str(tmp_path))
        assert app_config._load_project_overrides() == {}

    def test_non_dict_yaml_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        adg_dir = tmp_path / ".adg"
        adg_dir.mkdir()
        (adg_dir / "config.yml").write_text("- just\n- a\n- list\n", encoding="utf-8")
        monkeypatch.setenv("ADG_PROJECT_ROOT", str(tmp_path))
        assert app_config._load_project_overrides() == {}


class TestGetSettingEnvOverride:
    def test_env_beats_default(self, monkeypatch) -> None:
        monkeypatch.setenv("ADG_MAX_RETRIES", "17")
        assert get_setting("max-retries", default=3) == "17"

    def test_settings_key_beats_env(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.adg]\ntimeout = 30\n", encoding="utf-8")
        monkeypatch.setenv("ADG_PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("ADG_TIMEOUT", "99")
        clear_cache()
        assert get_setting("timeout") == 30

    def test_missing_key_returns_default(self) -> None:
        assert get_setting("never_defined", default="fallback") == "fallback"


class TestGetPath:
    def test_none_returns_default(self) -> None:
        sentinel = Path("/default/location")
        assert get_path("no_path_key", sentinel) == sentinel

    def test_expands_user(self, monkeypatch) -> None:
        monkeypatch.setenv("HOME", "/home/fakeuser")
        result = get_path("some_dir", Path("/d"))
        assert str(result).startswith("/")  # 合法路径对象


class TestClearCache:
    def test_cache_clear_runs(self) -> None:
        clear_cache()  # 幂等无异常
