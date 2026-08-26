"""config/loader.py 覆盖攻坚 (10%→80%+)。

覆盖:
- _deep_merge 深合并/列表去重/覆盖语义
- _dataclass_to_dict 递归转换
- _parse_env_path 环境变量路径解析
- _set_nested_value 类型推断(bool/int/float/str)
- _dict_to_config / _convert_* 嵌套 dataclass 转换
- YAML/TOML/CFG 三格式加载与 extends 继承链
- load_config 缓存 / get_config / reload_config / watch_config / create_default_config
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

import tools.scripts.config.loader as loader
from tools.scripts.config.loader import (
    _dataclass_to_dict,
    _deep_merge,
    _dict_to_config,
    _load_cfg_config,
    _load_toml_config,
    _parse_env_path,
    _set_nested_value,
    create_default_config,
    get_config,
    load_config,
    reload_config,
)
from tools.scripts.config.models import GovernanceConfig, SeverityLevel, ToolCategory


@pytest.fixture(autouse=True)
def _reset_config_state() -> Any:
    """每个测试前后重置全局配置缓存。"""
    loader._config_instance = None
    loader._config_mtime = 0.0
    loader._config_path = None
    yield
    loader._config_instance = None
    loader._config_mtime = 0.0
    loader._config_path = None


class TestDeepMerge:
    def test_override_scalar(self) -> None:
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_recursive_dict_merge(self) -> None:
        out = _deep_merge({"x": {"a": 1, "b": 2}}, {"x": {"b": 3}})
        assert out == {"x": {"a": 1, "b": 3}}

    def test_list_merge_dedup_preserve_order(self) -> None:
        out = _deep_merge({"l": ["a", "b"]}, {"l": ["b", "c"]})
        assert out == {"l": ["a", "b", "c"]}

    def test_new_key_added(self) -> None:
        assert _deep_merge({}, {"n": 1}) == {"n": 1}


class TestDataclassToDict:
    def test_nested_dataclass(self) -> None:
        from dataclasses import dataclass, field

        @dataclass
        class Inner:
            v: int = 1

        @dataclass
        class Outer:
            inner: Inner = field(default_factory=Inner)
            items: list[int] = field(default_factory=lambda: [1, 2])

        d: dict[str, Any] = _dataclass_to_dict(Outer())
        assert d == {"inner": {"v": 1}, "items": [1, 2]}

    def test_passthrough_scalars(self) -> None:
        assert _dataclass_to_dict([1, "a"]) == [1, "a"]
        assert _dataclass_to_dict({"k": 3}) == {"k": 3}


class TestEnvPathParsing:
    def test_known_section_split(self) -> None:
        assert _parse_env_path("JCODE_GOVERNANCE_PARALLEL_MAX_WORKERS", "JCODE_GOVERNANCE_") == [
            "parallel",
            "max_workers",
        ]

    def test_unknown_section_fallback(self) -> None:
        parts = _parse_env_path("JCODE_GOVERNANCE_CUSTOM_FOO_BAR", "JCODE_GOVERNANCE_")
        assert parts[0] == "custom"

    def test_set_nested_bool_int_float_str(self) -> None:
        d: dict[str, Any] = {}
        _set_nested_value(d, ["s", "b"], "true")
        _set_nested_value(d, ["s", "i"], "42")
        _set_nested_value(d, ["s", "f"], "3.5")
        _set_nested_value(d, ["s", "t"], "hello")
        assert d == {"s": {"b": True, "i": 42, "f": 3.5, "t": "hello"}}


class TestDictToConfig:
    def test_full_roundtrip(self) -> None:
        gov = GovernanceConfig()
        d: dict[str, Any] = {
            "baseline": {"enabled": False},
            "quality_gates": {"strict": {"require_zero_new_warnings": True}},
            "exceptions": [{"id": "e1", "rule": "R1", "paths": ["tests/*"]}],
            "default_tools": {"lint": {"command": "ruff"}},
        }
        cfg = _dict_to_config({**d})
        assert cfg.baseline.enabled is False
        assert cfg.quality_gates["strict"].require_zero_new_warnings is True
        assert cfg.exceptions[0].rule == "R1"
        assert cfg.default_tools[ToolCategory.LINT].command == "ruff"
        # 默认值不受影响
        assert cfg.version == gov.version or cfg.version == 1

    def test_severity_threshold_enum(self) -> None:
        cfg = _dict_to_config({"default_tools": {"lint": {"command": "x", "severity_threshold": "error"}}})
        assert cfg.default_tools[ToolCategory.LINT].severity_threshold == SeverityLevel.ERROR


class TestFormatLoaders:
    def test_toml_config(self, tmp_path: Path) -> None:
        p = tmp_path / "pyproject.toml"
        p.write_text('[tool.jcode.governance]\ncustom = { team = "core" }\n')
        out = _load_toml_config(p)
        assert out == {"custom": {"team": "core"}}

    def test_toml_missing_section(self, tmp_path: Path) -> None:
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "x"\n')
        assert not _load_toml_config(p)  # 缺 governance section → 空 dict

    def test_cfg_config(self, tmp_path: Path) -> None:
        p = tmp_path / "setup.cfg"
        p.write_text("[jcode:governance]\nversion = 1\n")
        out = _load_cfg_config(p)
        assert out is not None and "version" in out

    def test_load_missing_file(self, tmp_path: Path) -> None:
        from tools.scripts.config.loader import _load_yaml_file

        assert _load_yaml_file(tmp_path / "nope.yml") is None


class TestLoadConfig:
    def _isolate_cwd(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".jcode").mkdir(exist_ok=True)
        return tmp_path

    def test_yaml_file_loaded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        (tmp_path / ".jcode" / "governance.yaml").write_text("baseline:\n  enabled: false\n")
        cfg = load_config()
        assert cfg.baseline.enabled is False
        assert loader._config_mtime != 0.0

    def test_cache_hit_when_mtime_unchanged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        (tmp_path / ".jcode" / "governance.yaml").write_text("baseline:\n  enabled: false\n")
        first = load_config()
        second = load_config()
        assert first is second

    def test_reload_forces_reread(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        f = tmp_path / ".jcode" / "governance.yaml"
        f.write_text("baseline:\n  enabled: false\n")
        assert load_config().baseline.enabled is False
        f.write_text("baseline:\n  enabled: true\n")
        assert reload_config().baseline.enabled is True

    def test_explicit_path_argument(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        custom = tmp_path / "sub" / "gov.yaml"
        custom.parent.mkdir()
        custom.write_text("parallel:\n  max_workers: 7\n")
        cfg = load_config(custom)
        assert cfg.parallel.max_workers == 7

    def test_no_file_uses_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        assert isinstance(load_config(), GovernanceConfig)

    def test_extends_chain_merge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        (tmp_path / "base.yaml").write_text(
            "baseline:\n  enabled: false\n  path: base.json\nsecrets:\n  scan_workspace: true\n"
        )
        main_cfg = tmp_path / "governance.yaml"
        main_cfg.write_text("extends: [base.yaml]\nbaseline:\n  path: override.json\n")
        cfg = load_config(main_cfg)
        assert cfg.baseline.path == "override.json"  # 本地覆盖
        assert cfg.secrets.scan_workspace is True  # 继承保留

    def test_env_overrides_applied(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        monkeypatch.setenv("JCODE_GOVERNANCE_PARALLEL_MAX_WORKERS", "12")
        cfg = load_config()
        assert cfg.parallel.max_workers == 12

    def test_corrupt_yaml_falls_back_to_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._isolate_cwd(monkeypatch, tmp_path)
        (tmp_path / ".jcode" / "governance.yaml").write_text("{broken yaml::::")
        assert isinstance(load_config(), GovernanceConfig)


class TestSingletonAndWatch:
    def test_get_config_lazy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = get_config()
        assert isinstance(cfg, GovernanceConfig)

    def test_create_default_config(self, tmp_path: Path) -> None:
        out = tmp_path / "new_gov.yaml"
        create_default_config(out)
        assert out.exists()
        cfg = load_config(out)
        assert isinstance(cfg, GovernanceConfig)

    def test_watch_config_triggers_callback_on_change(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """watcher 监听全局 _config_path(需先 load_config 确定路径)。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".jcode").mkdir()
        f = tmp_path / ".jcode" / "governance.yaml"
        f.write_text("version: 1\n")
        load_config()  # 设置全局 _config_path

        fired = threading.Event()

        def cb() -> None:
            fired.set()

        t = loader.watch_config(cb, interval=0.05)
        try:
            time.sleep(0.15)
            f.write_text("version: 2\n")  # mtime 变化
            assert fired.wait(timeout=5), "回调未被触发"
        finally:
            t.join(timeout=1)
