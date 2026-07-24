"""Tests for add_navigation.py."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.scripts.add_navigation import (
    add_navigation_to_doc,
    get_navigation,
    main,
)


class TestGetNavigation(unittest.TestCase):
    """Test navigation generation."""

    def test_generates_navigation_for_efficiency_doc(self):
        """Should generate navigation for efficiency layer doc."""
        content = """---
title: Test
category: 效率层
tags: ['test']
---
# Test
"""
        nav = get_navigation(Path("test.md"), content)
        self.assertIn("## 导航", nav)
        self.assertIn("效率层", nav)
        self.assertIn("[[docs/efficiency/", nav)

    def test_returns_empty_for_no_category(self):
        """Should return empty for doc without category."""
        content = """---
title: Test
---
# Test
"""
        nav = get_navigation(Path("test.md"), content)
        self.assertEqual(nav, "")

    def test_excludes_current_doc(self):
        """Should not include current doc in related links."""
        content = """---
title: Test
category: 效率层
---
# Test
"""
        nav = get_navigation(Path("full-cycle-workflow.md"), content)
        self.assertNotIn("full-cycle-workflow", nav)

    def test_limits_related_docs(self):
        """Should limit to 5 related docs."""
        content = """---
title: Test
category: 效率层
---
# Test
"""
        nav = get_navigation(Path("test.md"), content)
        link_count = nav.count("[[docs/efficiency/")
        self.assertLessEqual(link_count, 5)


class TestAddNavigationToDoc(unittest.TestCase):
    """Test adding navigation to docs."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.docs_dir = Path(self.test_dir) / "docs" / "efficiency"
        self.docs_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_adds_navigation(self):
        """Should add navigation section."""
        doc = self.docs_dir / "test.md"
        doc.write_text(
            """---
title: Test
category: 效率层
---
# Test
""",
            encoding="utf-8",
        )

        result = add_navigation_to_doc(doc)
        self.assertTrue(result)
        content = doc.read_text(encoding="utf-8")
        self.assertIn("## 导航", content)

    def test_skips_if_exists(self):
        """Should skip if navigation already exists."""
        doc = self.docs_dir / "test.md"
        doc.write_text(
            """---
title: Test
## 导航
- [[docs/efficiency/other|Other]]
""",
            encoding="utf-8",
        )

        result = add_navigation_to_doc(doc)
        self.assertFalse(result)

    def test_skips_no_category(self):
        """Should skip if no category."""
        doc = self.docs_dir / "test.md"
        doc.write_text(
            """---
title: Test
---
# Test
""",
            encoding="utf-8",
        )

        result = add_navigation_to_doc(doc)
        self.assertFalse(result)


class TestMain(unittest.TestCase):
    """Test main function."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.docs_dir = Path(self.test_dir) / "docs" / "efficiency"
        self.docs_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_updates_multiple_docs(self):
        """Should update multiple docs."""
        for i in range(3):
            doc = self.docs_dir / f"doc{i}.md"
            doc.write_text(
                f"""---
title: Doc {i}
category: 效率层
---
# Doc {i}
""",
                encoding="utf-8",
            )

        # Run main with patched docs_dir
        from unittest.mock import patch

        with patch("tools.scripts.add_navigation.Path") as mock_path:
            mock_path.return_value = self.docs_dir
            # Just verify it runs without error
            main()


if __name__ == "__main__":
    unittest.main()
