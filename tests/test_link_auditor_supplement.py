"""Supplementary tests for link_auditor.py to improve coverage from 55% to 80%+."""

import os
import shutil
import tempfile
import unittest

from tools.scripts.link_auditor import (
    _build_index,
    _check_target,
    _strip_code_blocks,
    check_all_links,
    find_broken_links_with_index,
)


class TestFindBrokenLinksWithIndex(unittest.TestCase):
    """Test find_broken_links_with_index function."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.test_dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_with_external_index_valid_link(self):
        """Link resolving via external index should not be broken."""
        with open(os.path.join(self.test_dir, "target.md"), "w") as f:
            f.write("content")
        index = _build_index(self.test_dir)
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[target.md]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_broken_link(self):
        """Link not in external index should be reported as broken."""
        index = {}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[nonexistent]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0][1], "nonexistent")

    def test_with_external_index_skips_http(self):
        """HTTP links should be skipped."""
        index = {}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[https://example.com]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_skips_anchor(self):
        """Anchor links should be skipped."""
        index = {}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[#Heading]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_skips_placeholders(self):
        """Template placeholders should be skipped."""
        index = {}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[{placeholder}}]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_skips_template_dirs(self):
        """Template directories should be skipped."""
        template_dir = os.path.join(self.test_dir, ".github", "PULL_REQUEST_TEMPLATE")
        os.makedirs(template_dir, exist_ok=True)
        with open(os.path.join(template_dir, "template.md"), "w") as f:
            f.write("[[broken]]")
        index = {}
        broken = find_broken_links_with_index(self.test_dir, index)
        # Should not include files from template directories
        for file, _ in broken:
            self.assertNotIn("PULL_REQUEST_TEMPLATE", file)

    def test_with_external_index_multiple_files(self):
        """Should check all files in directory."""
        index = {}
        with open(os.path.join(self.test_dir, "a.md"), "w") as f:
            f.write("[[missing1]]")
        with open(os.path.join(self.test_dir, "b.md"), "w") as f:
            f.write("[[missing2]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 2)

    def test_with_external_index_display_text(self):
        """Display text after pipe should not affect resolution."""
        index = {"target": "target.md"}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[target|Display Text]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_backslash_pipe(self):
        """Backslash-pipe separator should be handled."""
        index = {"target": "target.md"}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[target\\|Display]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_non_md_files_skipped(self):
        """Non-markdown files should be skipped."""
        index = {}
        with open(os.path.join(self.test_dir, "notes.txt"), "w") as f:
            f.write("[[missing]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        self.assertEqual(len(broken), 0)

    def test_with_external_index_code_blocks_stripped(self):
        """Code blocks should be stripped before checking links."""
        index = {}
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("```toml\n[[fake-link]]\n```\n\n[[another-fake]]")
        broken = find_broken_links_with_index(self.test_dir, index)
        # Should only find "another-fake", not "fake-link"
        targets = [b[1] for b in broken]
        self.assertIn("another-fake", targets)
        self.assertNotIn("fake-link", targets)


class TestCheckAllLinks(unittest.TestCase):
    """Test check_all_links function."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.test_dir = "test_check_all"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        os.chdir(self.original_dir)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_check_all_returns_true_when_no_broken(self):
        """Should return True when no broken links found."""
        os.chdir(self.test_dir)
        # Create a docs directory with valid links
        os.makedirs("docs", exist_ok=True)
        with open("docs/target.md", "w") as f:
            f.write("content")
        with open("docs/source.md", "w") as f:
            f.write("[[target.md]]")
        # Create case-studies and examples dirs
        os.makedirs("case-studies", exist_ok=True)
        os.makedirs("examples", exist_ok=True)
        result = check_all_links()
        self.assertTrue(result)

    def test_check_all_returns_false_when_broken(self):
        """Should return False when broken links found."""
        os.chdir(self.test_dir)
        os.makedirs("docs", exist_ok=True)
        with open("docs/broken.md", "w") as f:
            f.write("[[nonexistent]]")
        result = check_all_links()
        self.assertFalse(result)

    def test_check_all_handles_missing_dirs(self):
        """Should handle missing directories gracefully."""
        os.chdir(self.test_dir)
        # No docs, case-studies, or examples dirs
        result = check_all_links()
        # Should not crash
        self.assertIn(result, [True, False])

    def test_check_all_cross_directory_links(self):
        """Cross-directory wikilinks should resolve."""
        os.chdir(self.test_dir)
        os.makedirs("docs", exist_ok=True)
        os.makedirs("examples", exist_ok=True)
        # Create target in docs
        with open("docs/target.md", "w") as f:
            f.write("content")
        # Create source in examples that links to docs/target
        with open("examples/source.md", "w") as f:
            f.write("[[docs/target.md]]")
        result = check_all_links()
        self.assertTrue(result)


class TestBuildIndex(unittest.TestCase):
    """Test _build_index function edge cases."""

    def setUp(self):
        self.test_dir = "test_build_index"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_index_contains_basename(self):
        """Index should contain basename without extension."""
        with open(os.path.join(self.test_dir, "MyFile.md"), "w") as f:
            f.write("content")
        index = _build_index(self.test_dir)
        self.assertIn("MyFile", index)

    def test_index_contains_relative_path(self):
        """Index should contain relative path."""
        with open(os.path.join(self.test_dir, "file.md"), "w") as f:
            f.write("content")
        index = _build_index(self.test_dir)
        self.assertIn("file.md", index)

    def test_index_first_encountered_wins(self):
        """First file with same basename should win."""
        os.makedirs(os.path.join(self.test_dir, "sub"), exist_ok=True)
        with open(os.path.join(self.test_dir, "dup.md"), "w") as f:
            f.write("first")
        with open(os.path.join(self.test_dir, "sub", "dup.md"), "w") as f:
            f.write("second")
        index = _build_index(self.test_dir)
        self.assertEqual(index["dup"], "dup.md")

    def test_index_empty_directory(self):
        """Empty directory should produce empty index."""
        index = _build_index(self.test_dir)
        self.assertEqual(len(index), 0)

    def test_index_non_md_files_ignored(self):
        """Non-markdown files should not be in index."""
        with open(os.path.join(self.test_dir, "file.txt"), "w") as f:
            f.write("text")
        with open(os.path.join(self.test_dir, "file.py"), "w") as f:
            f.write("code")
        index = _build_index(self.test_dir)
        self.assertEqual(len(index), 0)


class TestCheckTargetEdgeCases(unittest.TestCase):
    """Test _check_target edge cases."""

    def setUp(self):
        self.test_dir = "test_check_edge"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_check_target_nonexistent_returns_false(self):
        """Target that doesn't exist should return False."""
        index = {}
        result = _check_target("totally_nonexistent", index, self.test_dir, self.test_dir)
        self.assertFalse(result)

    def test_check_target_trailing_backslash_stripped(self):
        """Trailing backslash should be stripped from target."""
        os.makedirs(os.path.join(self.test_dir, "dir"), exist_ok=True)
        with open(os.path.join(self.test_dir, "dir", "README.md"), "w") as f:
            f.write("readme")
        index = _build_index(self.test_dir)
        result = _check_target("dir\\", index, self.test_dir, self.test_dir)
        self.assertTrue(result)

    def test_check_target_md_extension_appended(self):
        """Should try appending .md extension."""
        with open(os.path.join(self.test_dir, "target.md"), "w") as f:
            f.write("content")
        index = _build_index(self.test_dir)
        # "target" not in index, but "target.md" is
        result = _check_target("target", index, self.test_dir, self.test_dir)
        self.assertTrue(result)


class TestStripCodeBlocksEdgeCases(unittest.TestCase):
    """Test _strip_code_blocks edge cases."""

    def test_nested_fenced_blocks(self):
        """Nested fenced blocks should be handled."""
        content = "Outer\n```\nInner ``` code ```\n```\n[[real]]"
        cleaned = _strip_code_blocks(content)
        self.assertNotIn("[[fake]]", cleaned)
        self.assertIn("[[real]]", cleaned)

    def test_multiple_code_blocks(self):
        """Multiple code blocks should all be stripped."""
        content = "```python\n[[link1]]\n```\nText\n```js\n[[link2]]\n```\n[[real]]"
        cleaned = _strip_code_blocks(content)
        self.assertNotIn("[[link1]]", cleaned)
        self.assertNotIn("[[link2]]", cleaned)
        self.assertIn("[[real]]", cleaned)

    def test_empty_content(self):
        """Empty content should return empty."""
        cleaned = _strip_code_blocks("")
        self.assertEqual(cleaned, "")

    def test_no_code_blocks(self):
        """Content without code blocks should be unchanged."""
        content = "Plain text [[link]] here"
        cleaned = _strip_code_blocks(content)
        self.assertEqual(cleaned, content)


if __name__ == "__main__":
    unittest.main()
