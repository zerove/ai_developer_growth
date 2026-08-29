"""Unit tests for tools/scripts/adg_cli/fix.py.

补 tests/test_adg_cli_v2.py (只测 1 个 fix_file/fix_directory) 不足,
直接测三个函数的边界与错误路径.

提升覆盖率 47.5% -> 85%+.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.scripts.adg_cli.fix import _apply_fix, fix_directory, fix_file


class TestApplyFix:
    """_apply_fix 单条规则的 pattern+replacement 应用."""

    def test_no_pattern_returns_unchanged(self) -> None:
        """缺少 pattern 时返回原内容."""
        content = "x = 1"
        new, modified = _apply_fix(content, "r1", {"replacement": "y = 2"})
        assert new == "x = 1"
        assert modified is False

    def test_no_replacement_returns_unchanged(self) -> None:
        """replacement 为 None 时跳过."""
        content = "x = 1"
        new, modified = _apply_fix(content, "r1", {"pattern": "x = 1", "replacement": None})
        assert new == "x = 1"
        assert modified is False

    def test_no_match_returns_unchanged(self) -> None:
        """无匹配时不修改."""
        content = "hello world"
        new, modified = _apply_fix(content, "r1", {"pattern": "foo", "replacement": "bar"})
        assert new == "hello world"
        assert modified is False

    def test_match_replaces(self) -> None:
        """匹配时返回新内容 + modified=True."""
        content = "x = 1; y = 2"
        new, modified = _apply_fix(content, "r1", {"pattern": "x = 1", "replacement": "x = 99"})
        assert "x = 99" in new
        assert modified is True


class TestFixFile:
    """fix_file 单文件应用."""

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        """文件不存在时返回 errors=1."""
        result = fix_file(tmp_path / "missing.py")
        assert result == {"fixed": 0, "skipped": 0, "errors": 1}

    def test_skips_when_no_rules_match(self, tmp_path: Path) -> None:
        """无规则匹配时不修改."""
        f = tmp_path / "clean.py"
        f.write_text("# clean code; no fix needed")
        result = fix_file(f, rule_ids=["non-existent-rule"])
        assert result["errors"] == 0
        assert f.read_text() == "# clean code; no fix needed"

    def test_apply_real_rule(self, tmp_path: Path) -> None:
        """真实规则 py-bare-except 应被应用."""
        f = tmp_path / "fixable.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        result = fix_file(f)
        assert result["errors"] == 0
        assert "except Exception:" in f.read_text()

    def test_unicode_decode_error_returns_error(self, tmp_path: Path) -> None:
        """二进制文件读取失败时返回 errors=1."""
        f = tmp_path / "binary.py"
        # 构造一个让 read_text 失败的字节序列
        f.write_bytes(b"\xc3\xbf\xc3\xbe\xfd\xfenot utf-8")
        result = fix_file(f)
        assert result["errors"] == 1

    def test_write_error_returns_error(self, tmp_path: Path) -> None:
        """写回失败时返回 errors=1."""
        f = tmp_path / "fixable.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            result = fix_file(f)
        assert result["errors"] == 1


class TestFixDirectory:
    """fix_directory 目录批量."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """空目录返回零值."""
        result = fix_directory(tmp_path)
        assert result["files"] == 0
        assert result["fixed"] == 0

    def test_skips_skipped_dirs(self, tmp_path: Path) -> None:
        """__pycache__/.git 等应跳过."""
        skip_dir = tmp_path / "__pycache__"
        skip_dir.mkdir()
        f = skip_dir / "x.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        result = fix_directory(tmp_path)
        assert result["files"] == 0

    def test_skips_skip_extensions(self, tmp_path: Path) -> None:
        """.pyc 等应跳过."""
        f = tmp_path / "x.pyc"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        result = fix_directory(tmp_path)
        assert result["files"] == 0

    def test_filters_by_language(self, tmp_path: Path) -> None:
        """language=python 只修 Python."""
        py = tmp_path / "x.py"
        py.write_text("try:\n    pass\nexcept:\n    pass\n")
        js = tmp_path / "y.js"
        js.write_text("if (x == null) {}")
        fix_directory(tmp_path, language="python")
        assert "except Exception:" in py.read_text()
        assert "if (x == null) {}" in js.read_text()

    def test_no_language_means_all(self, tmp_path: Path) -> None:
        """language=None 时所有适用."""
        py = tmp_path / "x.py"
        py.write_text("try:\n    pass\nexcept:\n    pass\n")
        fix_directory(tmp_path, language=None)
        assert "except Exception:" in py.read_text()

    def test_processes_multiple_files(self, tmp_path: Path) -> None:
        """多文件被批量处理."""
        for i in range(3):
            (tmp_path / f"f{i}.py").write_text("try:\n    pass\nexcept:\n    pass\n")
        result = fix_directory(tmp_path)
        assert result["files"] == 3
        assert result["fixed"] >= 3
