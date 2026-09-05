"""Tests for rule_loader._rules_hash_cached + _rules_hash (Phase 32 子任务 2c).

覆盖 5 个分支:
- 多文件 hash (mock 真实 yml)
- 部分文件不存在 (跳过)
- OSError 兜底
- LRU cache (同 (lang, dir) 二次调用命中)
- _rules_hash 默认 framework_dir

详见 ADR-030 Phase 32 子任务分解 + ADR-033 (LRU 测试设计)。

设计要点:
- _rules_hash_cached 是 @lru_cache 装饰, 缓存按 (language, dir) 元组
- 测试前清空缓存 (lru_cache.cache_clear())
- 测试用 tmp_path 模拟 framework_dir
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tools.scripts.rules_engine.rule_loader import (
    _rules_hash,
    _rules_hash_cached,
)


@pytest.fixture
def framework_with_rules(tmp_path: Path) -> Path:
    """创建 framework_dir 模拟结构:
    - languages/python/rules.d/anti_patterns.yml
    - common/security.yml
    """
    lang_rules = tmp_path / "languages" / "python" / "rules.d"
    lang_rules.mkdir(parents=True)
    (lang_rules / "anti_patterns.yml").write_text("python_rules: v1\n")

    common = tmp_path / "common"
    common.mkdir()
    (common / "security.yml").write_text("security_rules: v1\n")

    return tmp_path


@pytest.fixture(autouse=True)
def _clear_lru_cache() -> None:
    """确保每个测试前清空 _rules_hash_cached 的 LRU cache。"""
    _rules_hash_cached.cache_clear()
    yield
    _rules_hash_cached.cache_clear()


class TestRulesHashCached:
    """_rules_hash_cached() 多文件 hash + LRU + 兜底。"""

    def test_multi_file_hash_returns_sha256(self, framework_with_rules: Path) -> None:
        """多个文件存在 → SHA-256 hex (空文件也至少64字符空 hash)。"""
        result = _rules_hash_cached("python", str(framework_with_rules))
        assert len(result) == 64
        # 验证是真实的 SHA-256 (来自两个文件内容)
        expected_input = b"python_rules: v1\n\x00security_rules: v1\n\x00"
        expected = hashlib.sha256(expected_input).hexdigest()
        assert result == expected

    def test_missing_files_return_zero_byte_hash(self, tmp_path: Path) -> None:
        """两个文件都不存在 → SHA-256(empty) (空 digest.hexdigest())。"""
        result = _rules_hash_cached("python", str(tmp_path))
        assert result == hashlib.sha256(b"").hexdigest()

    def test_only_one_file_exists(self, framework_with_rules: Path) -> None:
        """只有一个文件存在 → 仍能 hash (缺失文件跳过)。"""
        # 删除 common/security.yml
        (framework_with_rules / "common" / "security.yml").unlink()
        result = _rules_hash_cached("python", str(framework_with_rules))
        assert len(result) == 64
        # 验证只 hash 了 language 文件
        expected = hashlib.sha256(b"python_rules: v1\n\x00").hexdigest()
        assert result == expected

    def test_os_error_returns_empty_string(self, framework_with_rules: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """read_bytes 抛 OSError → \"\" (兜底, 不抛异常)。"""
        if os.geteuid() == 0:
            pytest.skip("root 用户可绕过文件权限")

        def boom(self: Path) -> bytes:  # noqa: ARG001
            raise PermissionError("simulated")

        monkeypatch.setattr(Path, "read_bytes", boom)
        result = _rules_hash_cached("python", str(framework_with_rules))
        assert result == ""

    def test_lru_cache_hit_same_args(self, framework_with_rules: Path) -> None:
        """同 (language, dir) 二次调用命中缓存 (返回相同值)。"""
        # 第一次: 计算 hash
        first = _rules_hash_cached("python", str(framework_with_rules))
        # 第二次: 应从缓存返回 (对象身份相同)
        second = _rules_hash_cached("python", str(framework_with_rules))
        assert first == second
        # 验证 cache_info 显示命中
        cache_info = _rules_hash_cached.cache_info()
        assert cache_info.hits >= 1

    def test_lru_cache_miss_different_args(self, framework_with_rules: Path, tmp_path: Path) -> None:
        """不同 (language, dir) 调用不命中缓存。"""
        # 创建另一个 framework dir
        other = tmp_path / "other_framework"
        (other / "languages" / "rust" / "rules.d").mkdir(parents=True)
        (other / "languages" / "rust" / "rules.d" / "anti_patterns.yml").write_text("rust: 1\n")
        (other / "common").mkdir()
        (other / "common" / "security.yml").write_text("sec: 1\n")

        # 第一次调用两个不同 dir
        hash_a = _rules_hash_cached("python", str(framework_with_rules))
        hash_b = _rules_hash_cached("rust", str(other))
        assert hash_a != hash_b  # 内容不同
        # cache_info 显示两个 misses
        cache_info = _rules_hash_cached.cache_info()
        assert cache_info.misses >= 2


class TestRulesHash:
    """_rules_hash() 公开 API: 默认 framework_dir = rules_dir()。"""

    def test_default_framework_dir(self, framework_with_rules: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """framework_dir=None → 使用 rules_dir() (项目默认目录)。

        注意: rule_loader 顶部 `from _common import rules_dir` 已绑定函数对象,
        所以 mock _common.rules_dir 无效, 必须 mock rule_loader.rules_dir。
        """
        from tools.scripts.rules_engine import rule_loader

        monkeypatch.setattr(rule_loader, "rules_dir", lambda: framework_with_rules)
        _rules_hash_cached.cache_clear()

        result = _rules_hash("python")
        # 验证走的是 mock 的路径
        expected = hashlib.sha256(b"python_rules: v1\n\x00security_rules: v1\n\x00").hexdigest()
        assert result == expected

    def test_explicit_framework_dir(self, framework_with_rules: Path) -> None:
        """传入 framework_dir → 使用传入路径 (不调 rules_dir())。"""
        result = _rules_hash("python", framework_with_rules)
        expected = hashlib.sha256(b"python_rules: v1\n\x00security_rules: v1\n\x00").hexdigest()
        assert result == expected
