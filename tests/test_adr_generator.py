"""Tests for adr_generator.py"""

import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock openai 等 LLM 客户端模块（在 import adr_generator 前）
mock_openai = MagicMock()
sys.modules["openai"] = mock_openai

from tools.scripts import adr_generator  # noqa: E402
from tools.scripts.adr_generator import (  # noqa: E402
    generate_from_llm,
    generate_from_llm_mode,
    generate_interactive,
    main,
    save_adr,
)


class TestGenerateFromLLM(unittest.TestCase):
    """Test LLM-based ADR generation."""

    @patch.object(adr_generator, "_get_llm_client")
    def test_generate_from_llm_returns_string(self, mock_get_llm):
        """Test that generate_from_llm returns a string."""
        mock_llm_class = MagicMock()
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "## Context\nTest context"
        mock_llm_class.return_value = mock_llm
        mock_get_llm.return_value = mock_llm_class

        result = generate_from_llm("Test Title", "Test brief")
        self.assertIsInstance(result, str)
        self.assertIn("Context", result)

    @patch.object(adr_generator, "_get_llm_client")
    def test_generate_from_llm_handles_empty_response(self, mock_get_llm):
        """Test that generate_from_llm handles empty LLM response."""
        mock_llm_class = MagicMock()
        mock_llm = MagicMock()
        mock_llm.generate.return_value = ""
        mock_llm_class.return_value = mock_llm
        mock_get_llm.return_value = mock_llm_class

        result = generate_from_llm("Test Title", "Test brief")
        self.assertEqual(result, "")


class TestGenerateInteractive(unittest.TestCase):
    """Test interactive ADR generation."""

    @patch.object(adr_generator, "_interactive", return_value=True)
    @patch(
        "builtins.input",
        side_effect=[
            "Test Title",
            "Context",
            "Alternatives",
            "Decision",
            "Consequences",
        ],
    )
    def test_generate_interactive_returns_tuple(self, mock_input, _mock_tty):
        """Test that generate_interactive returns (title, body) tuple."""
        title, body = generate_interactive()
        self.assertEqual(title, "Test Title")
        self.assertIn("## Context", body)
        self.assertIn("## Alternatives", body)
        self.assertIn("## Decision", body)
        self.assertIn("## Consequences", body)


class TestSaveAdr(unittest.TestCase):
    """Test ADR saving functionality."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.tmp_dir)

    def test_save_adr_creates_file(self):
        """Test that save_adr creates a file in docs/adr/."""
        filepath = save_adr("Test Decision", "## Context\nTest content")
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.startswith("docs/adr/"))

        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Test Decision", content)
        self.assertIn("## Context", content)

    def test_save_adr_increments_index(self):
        """Test that save_adr increments ADR index."""
        filepath1 = save_adr("First Decision", "Body 1")
        filepath2 = save_adr("Second Decision", "Body 2")

        self.assertIn("ADR-001", filepath1)
        self.assertIn("ADR-002", filepath2)

    def test_save_adr_filename_format(self):
        """Test that save_adr generates correct filename format."""
        filepath = save_adr("My Test Decision", "Body")
        # 小写、连字符分隔；与 docs/adr/ 既有 ADR-0xx-slug.md 命名一致，
        # 且保证 ':' '/' 等字符不会进入文件名（Windows / zip 不接受）。
        self.assertIn("ADR-001-my-test-decision.md", filepath)
        self.assertNotIn(":", os.path.basename(filepath))

    def test_save_adr_includes_metadata(self):
        """Test that saved ADR includes status and date."""
        filepath = save_adr("Meta Test", "## Context\nTest")
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Accepted", content)
        self.assertIn("## Context", content)


if __name__ == "__main__":
    unittest.main()


class TestGenerateFromLLMMode(unittest.TestCase):
    """Test LLM mode ADR generation."""

    @patch.object(adr_generator, "_interactive", return_value=True)
    @patch("builtins.input", side_effect=["Test Title", "Test brief description", "y"])
    @patch.object(adr_generator, "generate_from_llm", return_value="## Context\nGenerated content")
    def test_generate_from_llm_mode_returns_tuple(self, mock_llm, mock_input, _mock_tty):
        """Test that generate_from_llm_mode returns (title, body) tuple."""
        title, body = generate_from_llm_mode()
        self.assertEqual(title, "Test Title")
        self.assertIn("Generated content", body)

    @patch.object(adr_generator, "_interactive", return_value=True)
    @patch(
        "builtins.input",
        side_effect=[
            "Test Title",
            "Test brief description",
            "n",
            "Fallback Title",
            "Context",
            "Alternatives",
            "Decision",
            "Consequences",
        ],
    )
    @patch.object(adr_generator, "generate_from_llm", return_value="## Context\nGenerated content")
    def test_generate_from_llm_mode_fallback_on_reject(self, mock_llm, mock_input, _mock_tty):
        """Test fallback to interactive when user rejects LLM output."""
        title, body = generate_from_llm_mode()
        self.assertEqual(title, "Fallback Title")
        self.assertIn("Context", body)
        self.assertIn("Alternatives", body)


class TestMain(unittest.TestCase):
    """Test main function."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.tmp_dir)

    @patch.object(adr_generator, "generate_from_llm", return_value="## Context\nTest")
    @patch.object(adr_generator, "save_adr")
    def test_main_llm_mode(self, mock_save, mock_llm):
        """LLM 模式：--title/--brief 直接作为输入，无需交互。"""
        self.assertEqual(main(["--title", "Test Title", "--brief", "Test brief"]), 0)
        mock_save.assert_called_once()

    @patch.object(adr_generator, "_interactive", return_value=True)
    @patch(
        "builtins.input",
        side_effect=[
            "Test Title",
            "Context",
            "Alternatives",
            "Decision",
            "Consequences",
        ],
    )
    @patch.object(adr_generator, "save_adr")
    def test_main_interactive_mode(self, mock_save, mock_input, _mock_tty):
        """交互模式：--interactive 走逐字段输入。"""
        self.assertEqual(main(["--interactive"]), 0)
        mock_save.assert_called_once()

    @patch.object(adr_generator, "_interactive", return_value=True)
    @patch.object(adr_generator, "generate_from_llm", side_effect=Exception("LLM Error"))
    @patch.object(
        adr_generator,
        "generate_interactive",
        return_value=("Fallback Title", "## Context\nFallback"),
    )
    @patch.object(adr_generator, "save_adr")
    def test_main_llm_fallback_to_interactive(self, mock_save, mock_interactive, mock_llm, _mock_tty):
        """可交互时 LLM 失败降级到交互模式。"""
        self.assertEqual(main(["--title", "T"]), 0)
        mock_save.assert_called_once()
        mock_interactive.assert_called_once()

    @patch.object(adr_generator, "_interactive", return_value=False)
    @patch.object(adr_generator, "generate_from_llm", side_effect=Exception("LLM Error"))
    def test_main_llm_failure_non_interactive_exits_nonzero(self, mock_llm, _mock_tty):
        """回归防护：非交互 + LLM 失败必须退出 1，不得回退到 input() 抛 EOFError。"""
        self.assertEqual(main(["--title", "T"]), 1)


# ── 以下为本轮新增行为的回归防护 ──────────────────────────────────
# 用普通 pytest 类（非 unittest.TestCase），以便使用 tmp_path fixture。


class TestSlugifyIsFilesystemSafe:
    """早前 slug 用 title.replace(' ', '_')，标题里的 ':' 会直接进文件名。"""

    @pytest.mark.parametrize(
        "title",
        ["test: 文件计数断言", "a/b\\c", "why? what*", 'quote"x', "tab\tsep", "///"],
    )
    def test_no_unsafe_chars(self, title: str) -> None:
        slug = adr_generator._slugify(title)
        assert not re.search(r"[^A-Za-z0-9_-]", slug), f"slug 含非法字符: {slug!r}"

    def test_uses_dashes_matching_repo_convention(self) -> None:
        assert adr_generator._slugify("My Test Decision") == "my-test-decision"

    def test_empty_falls_back(self) -> None:
        assert adr_generator._slugify("///") == "adr"

    def test_length_capped(self) -> None:
        assert len(adr_generator._slugify("word " * 60)) <= 60


class TestNextAdrIndexUsesMax:
    """早前用 len(existing)+1，序号有缺口时会撞名并静默覆盖。"""

    def test_gap_does_not_collide(self, tmp_path: Path) -> None:
        (tmp_path / "ADR-001-a.md").write_text("x", encoding="utf-8")
        (tmp_path / "ADR-005-b.md").write_text("x", encoding="utf-8")
        assert adr_generator._next_adr_index(str(tmp_path)) == 6

    def test_ignores_non_adr_and_malformed(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("x", encoding="utf-8")
        (tmp_path / "ADR-abc.md").write_text("x", encoding="utf-8")
        (tmp_path / "ADR-003-c.md").write_text("x", encoding="utf-8")
        assert adr_generator._next_adr_index(str(tmp_path)) == 4

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert adr_generator._next_adr_index(str(tmp_path)) == 1


class TestSaveAdrNeverOverwrites:
    def test_same_title_twice_creates_two_files(self, tmp_path: Path) -> None:
        a = adr_generator.save_adr("Same Title", "body1", str(tmp_path))
        b = adr_generator.save_adr("Same Title", "body2", str(tmp_path))
        assert a != b
        assert Path(a).read_text(encoding="utf-8").endswith("body1")

    def test_guard_prevents_clobbering_existing_file(self, tmp_path: Path) -> None:
        """真正覆盖 save_adr 的后缀守卫。

        单纯"保存两次"并不能验证守卫——序号会自然递增（001 -> 002），
        文件名本来就不同。这里把 _next_adr_index 固定为 1，并预置一个
        同名文件，强制触发 os.path.exists 撞名分支。
        """
        existing = tmp_path / "ADR-001-same-title.md"
        existing.write_text("PRECIOUS", encoding="utf-8")
        with patch.object(adr_generator, "_next_adr_index", return_value=1):
            out = Path(adr_generator.save_adr("Same Title", "new-body", str(tmp_path)))
        assert out != existing, "撞名时必须另起文件名"
        assert existing.read_text(encoding="utf-8") == "PRECIOUS", "既有文件被覆盖了"
        assert out.read_text(encoding="utf-8").endswith("new-body")

    def test_respects_custom_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "elsewhere"
        out = adr_generator.save_adr("T", "b", str(target))
        assert Path(out).parent == target


class TestCliNonInteractive:
    """ADR-060：非交互环境（hook/CI）过去必然 EOFError 退出 1。"""

    def test_missing_title_fails_cleanly(self) -> None:
        with patch.object(adr_generator, "_interactive", return_value=False):
            assert adr_generator.main(["--pr", "1"]) == 1

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        with (
            patch.object(adr_generator, "generate_from_llm", return_value="## Context\nc"),
            patch.object(adr_generator, "_interactive", return_value=False),
        ):
            rc = adr_generator.main(["--title", "T", "--dry-run", "--adr-dir", str(tmp_path)])
        assert rc == 0
        assert list(tmp_path.iterdir()) == []

    def test_pr_ref_recorded_in_body(self, tmp_path: Path) -> None:
        with (
            patch.object(adr_generator, "generate_from_llm", return_value="## Context\nc"),
            patch.object(adr_generator, "_interactive", return_value=False),
        ):
            rc = adr_generator.main(["--title", "T", "--pr", "42", "--adr-dir", str(tmp_path)])
        assert rc == 0
        written = next(tmp_path.iterdir()).read_text(encoding="utf-8")
        assert "## 关联变更" in written
        assert "`42`" in written

    def test_llm_failure_non_interactive_exits_one(self) -> None:
        with (
            patch.object(adr_generator, "generate_from_llm", side_effect=RuntimeError("no key")),
            patch.object(adr_generator, "_interactive", return_value=False),
        ):
            assert adr_generator.main(["--title", "T"]) == 1

    def test_prompt_never_raises_eoferror(self) -> None:
        with patch.object(adr_generator, "_interactive", return_value=True):
            with patch("builtins.input", side_effect=EOFError):
                assert adr_generator._prompt("q: ", "fallback") == "fallback"

    def test_prompt_uses_default_without_tty(self) -> None:
        with patch.object(adr_generator, "_interactive", return_value=False):
            assert adr_generator._prompt("q: ", "fallback") == "fallback"
