import os
import shutil
import unittest
from pathlib import Path

from tools.scripts.check_metadata import check_metadata, extract_frontmatter, scan_directory


class TestExtractFrontmatter(unittest.TestCase):
    """Test YAML frontmatter extraction."""

    def test_valid_frontmatter(self):
        """Should extract key-value pairs from valid frontmatter."""
        content = """---
title: Test Title
description: A test
category: 效率层
tags: ['AI', 'test']
difficulty: 进阶
---

Body content"""
        fm, body = extract_frontmatter(content)
        self.assertEqual(fm["title"], "Test Title")
        self.assertEqual(fm["description"], "A test")
        self.assertEqual(fm["category"], "效率层")
        self.assertIn("AI", fm["tags"])
        self.assertEqual(fm["difficulty"], "进阶")
        self.assertIn("Body content", body)

    def test_no_frontmatter(self):
        """Should return empty dict when no frontmatter present."""
        content = "# Title\n\nSome content"
        fm, body = extract_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertEqual(body, content)

    def test_empty_frontmatter(self):
        """Should handle empty frontmatter."""
        content = "---\n---\n\nBody"
        fm, body = extract_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertIn("Body", body)

    def test_frontmatter_with_colons_in_value(self):
        """Should handle values containing colons."""
        content = """---
title: AI: A Revolution
description: About AI
---

Body"""
        fm, body = extract_frontmatter(content)
        self.assertEqual(fm["title"], "AI: A Revolution")
        self.assertEqual(fm["description"], "About AI")

    def test_frontmatter_with_multiline_value(self):
        """Should handle multiline values (only first line captured)."""
        content = """---
title: Single Line
description: Line1
  Line2
---

Body"""
        fm, body = extract_frontmatter(content)
        self.assertEqual(fm["title"], "Single Line")


class TestCheckMetadata(unittest.TestCase):
    """Test single file metadata checking."""

    def setUp(self):
        self.test_dir = "test_metadata"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_file = Path(self.test_dir) / "test.md"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_valid_file_no_issues(self):
        """File with all required fields should have no issues."""
        self.test_file.write_text("""---
title: Test
description: Desc
category: 效率层
tags: ['AI']
difficulty: 进阶
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertEqual(issues, [])

    def test_missing_title(self):
        """Should report missing title field."""
        self.test_file.write_text("""---
description: Desc
category: 效率层
tags: ['AI']
difficulty: 进阶
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("title" in i for i in issues))

    def test_missing_description(self):
        """Should report missing description field."""
        self.test_file.write_text("""---
title: Test
category: 效率层
tags: ['AI']
difficulty: 进阶
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("description" in i for i in issues))

    def test_missing_category(self):
        """Should report missing category field."""
        self.test_file.write_text("""---
title: Test
description: Desc
tags: ['AI']
difficulty: 中级
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("category" in i for i in issues))

    def test_missing_tags(self):
        """Should report missing tags field."""
        self.test_file.write_text("""---
title: Test
description: Desc
category: 效率层
difficulty: 中级
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("tags" in i for i in issues))

    def test_missing_difficulty(self):
        """Should report missing difficulty field."""
        self.test_file.write_text("""---
title: Test
description: Desc
category: 效率层
tags: ['AI']
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("difficulty" in i for i in issues))

    def test_invalid_category(self):
        """Should report invalid category."""
        self.test_file.write_text("""---
title: Test
description: Desc
category: 无效分类
tags: ['AI']
difficulty: 中级
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("Invalid category" in i for i in issues))

    def test_invalid_difficulty(self):
        """Should report invalid difficulty."""
        self.test_file.write_text("""---
title: Test
description: Desc
category: 效率层
tags: ['AI']
difficulty: 超级难
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("Invalid difficulty" in i for i in issues))

    def test_description_too_long(self):
        """Should report description exceeding 50 chars."""
        long_desc = "A" * 51
        self.test_file.write_text(f"""---
title: Test
description: {long_desc}
category: 效率层
tags: ['AI']
difficulty: 进阶
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertTrue(any("Description too long" in i for i in issues))

    def test_description_at_limit(self):
        """Description at exactly 50 chars should be OK."""
        desc = "A" * 50
        self.test_file.write_text(f"""---
title: Test
description: {desc}
category: 效率层
tags: ['AI']
difficulty: 进阶
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertFalse(any("Description too long" in i for i in issues))

    def test_all_valid_categories(self):
        """All valid categories should pass."""
        for cat in ["认知层", "学习层", "效率层", "工具层", "治理层"]:
            self.test_file.write_text(f"""---
title: Test
description: Desc
category: {cat}
tags: ['AI']
difficulty: 中级
---

# Content""", encoding="utf-8")
            issues = check_metadata(self.test_file)
            self.assertFalse(any("Invalid category" in i for i in issues), f"Failed for {cat}")

    def test_all_valid_difficulties(self):
        """All valid difficulties should pass."""
        for diff in ["入门", "基础", "进阶", "高级", "专家"]:
            self.test_file.write_text(f"""---
title: Test
description: Desc
category: 效率层
tags: ['AI']
difficulty: {diff}
---

# Content""", encoding="utf-8")
            issues = check_metadata(self.test_file)
            self.assertFalse(any("Invalid difficulty" in i for i in issues), f"Failed for {diff}")

    def test_file_read_error(self):
        """Should handle file read errors gracefully."""
        bad_file = Path(self.test_dir) / "nonexistent.md"
        issues = check_metadata(bad_file)
        self.assertTrue(any("Error reading file" in i for i in issues))

    def test_multiple_missing_fields(self):
        """Should report all missing fields at once."""
        self.test_file.write_text("""---
title: Test
---

# Content""", encoding="utf-8")
        issues = check_metadata(self.test_file)
        self.assertGreaterEqual(len(issues), 3)  # missing description, category, tags, difficulty


class TestScanDirectory(unittest.TestCase):
    """Test directory scanning."""

    def setUp(self):
        self.test_dir = "test_metadata_scan"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_scan_finds_issues(self):
        """Should find files with metadata issues."""
        (Path(self.test_dir) / "bad.md").write_text("# No frontmatter", encoding="utf-8")
        results = scan_directory(Path(self.test_dir))
        self.assertGreater(len(results), 0)

    def test_scan_ignores_valid_files(self):
        """Valid files should not appear in results."""
        (Path(self.test_dir) / "good.md").write_text("""---
title: Test
description: Desc
category: 效率层
tags: ['AI']
difficulty: 进阶
---

# Content""", encoding="utf-8")
        results = scan_directory(Path(self.test_dir))
        self.assertEqual(len(results), 0)

    def test_scan_skips_git_dir(self):
        """Should skip .git directories."""
        git_dir = Path(self.test_dir) / ".git"
        os.makedirs(git_dir, exist_ok=True)
        (git_dir / "file.md").write_text("# Git file", encoding="utf-8")
        results = scan_directory(Path(self.test_dir))
        # Should not include .git/file.md
        for key in results:
            self.assertNotIn(".git", key)

    def test_scan_empty_directory(self):
        """Empty directory should return empty results."""
        results = scan_directory(Path(self.test_dir))
        self.assertEqual(len(results), 0)

    def test_scan_nested_directories(self):
        """Should scan nested directories recursively."""
        sub_dir = Path(self.test_dir) / "sub"
        os.makedirs(sub_dir, exist_ok=True)
        (sub_dir / "nested.md").write_text("# No frontmatter", encoding="utf-8")
        results = scan_directory(Path(self.test_dir))
        self.assertGreater(len(results), 0)
        self.assertTrue(any("nested.md" in k for k in results))

    def test_scan_non_md_files_ignored(self):
        """Non-markdown files should be ignored."""
        (Path(self.test_dir) / "notes.txt").write_text("# Not markdown", encoding="utf-8")
        results = scan_directory(Path(self.test_dir))
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
