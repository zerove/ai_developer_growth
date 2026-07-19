import unittest
import os
import shutil
from tools.scripts.link_auditor import find_broken_links


class TestLinkAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_docs"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_find_broken_links(self):
        """One broken wikilink should be reported."""
        with open(os.path.join(self.test_dir, "broken.md"), "w") as f:
            f.write("[[nonexistent.md|Title]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0][1], "nonexistent.md")

    def test_valid_link_not_reported(self):
        """A wikilink pointing to an existing file should not appear."""
        with open(os.path.join(self.test_dir, "target.md"), "w") as f:
            f.write("content")
        with open(os.path.join(self.test_dir, "source.md"), "w") as f:
            f.write("[[target.md|Link]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)

    def test_external_urls_skipped(self):
        """http/https URLs should be ignored, not treated as broken."""
        with open(os.path.join(self.test_dir, "ext.md"), "w") as f:
            f.write("[[https://example.com|External]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)

    def test_anchor_links_skipped(self):
        """Anchor-only links (#heading) should be ignored."""
        with open(os.path.join(self.test_dir, "anchor.md"), "w") as f:
            f.write("[[#Section Title]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)

    def test_display_text_ignored(self):
        """The display text after | should not affect link resolution."""
        with open(os.path.join(self.test_dir, "a.md"), "w") as f:
            f.write("existing")
        with open(os.path.join(self.test_dir, "b.md"), "w") as f:
            f.write("[[a|任何显示文本]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)

    def test_empty_directory(self):
        """An empty directory should produce no broken links."""
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)

    def test_no_markdown_files(self):
        """Non-.md files should be skipped."""
        with open(os.path.join(self.test_dir, "notes.txt"), "w") as f:
            f.write("[[missing.md]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)

    def test_multiple_broken_links(self):
        """Multiple broken links in one file should all be reported."""
        with open(os.path.join(self.test_dir, "multi.md"), "w") as f:
            f.write("[[aaa]][[bbb]][[ccc]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 3)
        targets = {b[1] for b in broken}
        self.assertEqual(targets, {"aaa", "bbb", "ccc"})

    def test_basname_match(self):
        """Obsidian-style basename matching should resolve."""
        os.makedirs(os.path.join(self.test_dir, "sub"), exist_ok=True)
        with open(os.path.join(self.test_dir, "sub", "Deep.md"), "w") as f:
            f.write("deep content")
        with open(os.path.join(self.test_dir, "ref.md"), "w") as f:
            f.write("[[Deep]]")
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 0)


if __name__ == "__main__":
    unittest.main()
