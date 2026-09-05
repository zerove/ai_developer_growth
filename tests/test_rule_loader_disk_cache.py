"""Tests for rule_loader._load_disk_cache + _save_disk_cache (Phase 32 子任务 2b).

覆盖 4 个分支:
- _load_disk_cache: 文件不存在 / 正常 JSON / JSONDecodeError / OSError
- _save_disk_cache: mkdir + write / OSError 兜底

详见 ADR-030 Phase 32 子任务分解 + ADR-032 (mock 设计)。

设计要点:
- 模块级 _DISK_CACHE_FILE 是硬编码路径, 测试用 monkeypatch
  重定向到 tmp_path, 不污染真实缓存
- _DISK_CACHE_DIR 也需 monkeypatch, 否则 mkdir 会写真实路径
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.scripts.rules_engine import rule_loader
from tools.scripts.rules_engine.rule_loader import _load_disk_cache, _save_disk_cache


@pytest.fixture
def tmp_cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """重定向模块级 _DISK_CACHE_FILE + _DISK_CACHE_DIR 到 tmp_path。"""
    cache_dir = tmp_path / ".cache" / "rules_engine"
    cache_file = cache_dir / "rules_cache.json"
    monkeypatch.setattr(rule_loader, "_DISK_CACHE_DIR", cache_dir)
    monkeypatch.setattr(rule_loader, "_DISK_CACHE_FILE", cache_file)
    return cache_file


class TestLoadDiskCache:
    """_load_disk_cache() 4 个分支。"""

    def test_no_file_returns_empty(self, tmp_cache_path: Path) -> None:
        """文件不存在 → {} (不抛异常)。"""
        assert not tmp_cache_path.exists()
        result = _load_disk_cache()
        assert result == {}

    def test_valid_json_returns_parsed_dict(self, tmp_cache_path: Path) -> None:
        """正常 JSON → 解析后的 dict。"""
        tmp_cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"python": {"anti_patterns": [{"id": "x"}]}}
        tmp_cache_path.write_text(json.dumps(data))
        result = _load_disk_cache()
        assert result == data

    def test_invalid_json_returns_empty(self, tmp_cache_path: Path) -> None:
        """JSONDecodeError → {} (兜底, 不抛异常)。"""
        tmp_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_cache_path.write_text("{ invalid json [")
        result = _load_disk_cache()
        assert result == {}

    def test_empty_file_returns_empty(self, tmp_cache_path: Path) -> None:
        """空文件 → JSONDecodeError 兜底 → {}。"""
        tmp_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_cache_path.write_text("")
        result = _load_disk_cache()
        assert result == {}

    def test_os_error_on_read_returns_empty(self, tmp_cache_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """read_text 抛 OSError → {} 兜底。

        通过 monkeypatch Path.read_text 抛 PermissionError 模拟。
        """
        if os.geteuid() == 0:
            pytest.skip("root 用户可绕过文件权限")

        tmp_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_cache_path.write_text("{}")

        def boom(self: Path) -> str:  # noqa: ARG001
            raise PermissionError("simulated")

        monkeypatch.setattr(Path, "read_text", boom)
        result = _load_disk_cache()
        assert result == {}


class TestSaveDiskCache:
    """_save_disk_cache() 2 个分支: mkdir+write / OSError 兜底。"""

    def test_save_creates_directory_and_writes(self, tmp_cache_path: Path) -> None:
        """目录不存在时自动创建, 然后写入 JSON。"""
        assert not tmp_cache_path.parent.exists()
        data = {"python": {"x": 1}}
        _save_disk_cache(data)
        assert tmp_cache_path.parent.exists()
        assert json.loads(tmp_cache_path.read_text()) == data

    def test_save_overwrites_existing(self, tmp_cache_path: Path) -> None:
        """已存在文件被覆盖。"""
        tmp_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_cache_path.write_text('{"old": true}')
        new_data = {"new": 1}
        _save_disk_cache(new_data)
        assert json.loads(tmp_cache_path.read_text()) == new_data

    def test_save_os_error_silently_ignored(self, tmp_cache_path: Path) -> None:
        """OSError 兜底: write_text 抛 PermissionError → 静默忽略。

        mkdir + write 任何一步失败都被 except OSError 捕获。
        """
        if os.geteuid() == 0:
            pytest.skip("root 用户可绕过文件权限")

        # 让 mkdir 抛错 (用 chmod 0o000 父目录)
        tmp_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_cache_path.parent.chmod(0o000)
        try:
            # 调用应被兜底, 不抛异常
            _save_disk_cache({"x": 1})
        finally:
            tmp_cache_path.parent.chmod(0o755)
