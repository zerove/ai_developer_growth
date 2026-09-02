"""Tests for rule_loader._file_hash (Phase 32 子任务 2a).

覆盖 3 个分支:
- 文件存在 + 可读 → SHA-256 hex (64 字符)
- 文件不存在 → ""
- OSError (权限拒绝) → ""

详见 ADR-030 Phase 32 子任务分解。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tools.scripts.rules_engine.rule_loader import _file_hash


class TestFileHash:
    """_file_hash() SHA-256 计算 + 错误兜底。"""

    def test_existing_file_returns_sha256(self, tmp_path: Path) -> None:
        """文件存在时返回 SHA-256 hex 字符串 (64 字符)。"""
        target = tmp_path / "test.txt"
        target.write_bytes(b"hello world")
        result = _file_hash(target)
        assert len(result) == 64  # SHA-256 hex 长度
        # 验证是真实的 SHA-256
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert result == expected

    def test_empty_file_returns_sha256_of_empty(self, tmp_path: Path) -> None:
        """空文件返回 SHA-256(empty) hex。"""
        target = tmp_path / "empty.txt"
        target.write_bytes(b"")
        result = _file_hash(target)
        assert result == hashlib.sha256(b"").hexdigest()

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        """文件不存在返回空字符串 (而非抛异常)。"""
        target = tmp_path / "does_not_exist.txt"
        assert not target.exists()
        result = _file_hash(target)
        assert result == ""

    def test_permission_denied_returns_empty(self, tmp_path: Path) -> None:
        """文件存在但不可读 (权限拒绝) 时返回空字符串。

        注意: root 用户在 Linux 上可绕过文件权限检查 (CAP_DAC_OVERRIDE),
        所以此测试在 root 下会被跳过。详见 ADR-031。
        """
        if os.geteuid() == 0:
            pytest.skip("root 用户可绕过文件权限, 无法触发 OSError")

        target = tmp_path / "no_read.txt"
        target.write_bytes(b"secret")
        # 移除读权限 (chmod 0o000) — 用括号保证优先级
        target.chmod(0o000)
        try:
            result = _file_hash(target)
            # OSError 兜底 → ""
            assert result == ""
        finally:
            # 恢复权限以便 tmp_path 清理
            target.chmod(0o644)

    def test_binary_content_hash(self, tmp_path: Path) -> None:
        """二进制内容正确计算 SHA-256。"""
        target = tmp_path / "binary.bin"
        content = bytes(range(256))
        target.write_bytes(content)
        result = _file_hash(target)
        assert result == hashlib.sha256(content).hexdigest()

    def test_large_file_hash(self, tmp_path: Path) -> None:
        """大文件 (>1MB) 正确计算 SHA-256。"""
        target = tmp_path / "large.bin"
        content = b"x" * (1024 * 1024 + 100)  # ~1MB + 100 bytes
        target.write_bytes(content)
        result = _file_hash(target)
        assert result == hashlib.sha256(content).hexdigest()
