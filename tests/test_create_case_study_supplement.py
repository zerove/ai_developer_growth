"""Tests for create_case_study.py - improve coverage from 77% to 85%+."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.scripts.create_case_study import (
    create_case_study_structure,
    get_default_template,
)


class TestCreateCaseStudyStructure(unittest.TestCase):
    """Test case study directory creation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_creates_directory(self):
        """Should create the case study directory."""
        result = create_case_study_structure("Test Case", Path(self.test_dir))
        self.assertTrue(result.exists())
        self.assertTrue(result.is_dir())

    def test_creates_subdirectories(self):
        """Should create standard subdirectories."""
        result = create_case_study_structure("Test Case", Path(self.test_dir))
        self.assertTrue((result / "code").exists())
        self.assertTrue((result / "docs").exists())
        self.assertTrue((result / "tests").exists())
        self.assertTrue((result / "assets").exists())

    def test_creates_readme(self):
        """Should create README.md from template."""
        result = create_case_study_structure("Test Case", Path(self.test_dir))
        self.assertTrue((result / "README.md").exists())

    def test_readme_has_title(self):
        """README should contain the case name."""
        result = create_case_study_structure("My Project", Path(self.test_dir))
        content = (result / "README.md").read_text(encoding="utf-8")
        self.assertIn("My Project", content)

    def test_creates_doc_placeholders(self):
        """Should create placeholder docs."""
        result = create_case_study_structure("Test Case", Path(self.test_dir))
        self.assertTrue((result / "docs" / "PRD.md").exists())
        self.assertTrue((result / "docs" / "DESIGN.md").exists())
        self.assertTrue((result / "docs" / "RETROSPECTIVE.md").exists())

    def test_creates_gitkeep(self):
        """Should create .gitkeep files."""
        result = create_case_study_structure("Test Case", Path(self.test_dir))
        self.assertTrue((result / "code" / ".gitkeep").exists())
        self.assertTrue((result / "tests" / ".gitkeep").exists())
        self.assertTrue((result / "assets" / ".gitkeep").exists())

    def test_name_sanitized(self):
        """Directory name should be lowercase with hyphens."""
        result = create_case_study_structure("My Test Case", Path(self.test_dir))
        self.assertEqual(result.name, "my-test-case")

    def test_idempotent(self):
        """Running twice should not fail."""
        create_case_study_structure("Test Case", Path(self.test_dir))
        result = create_case_study_structure("Test Case", Path(self.test_dir))
        self.assertTrue(result.exists())

    def test_existing_docs_not_overwritten(self):
        """Existing doc files should not be overwritten."""
        case_dir = Path(self.test_dir) / "test-case"
        docs_dir = case_dir / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "PRD.md").write_text("existing PRD", encoding="utf-8")

        create_case_study_structure("Test Case", Path(self.test_dir))
        content = (docs_dir / "PRD.md").read_text(encoding="utf-8")
        self.assertEqual(content, "existing PRD")


class TestGetDefaultTemplate(unittest.TestCase):
    """Test default template generation."""

    def test_template_has_sections(self):
        """Template should contain required sections."""
        template = get_default_template()
        self.assertIn("## 背景", template)
        self.assertIn("## AI 协作过程", template)
        self.assertIn("## 效率对比", template)
        self.assertIn("## 关键洞察", template)
        self.assertIn("## 适用场景", template)
        self.assertIn("## 交付物清单", template)

    def test_template_has_placeholder(self):
        """Template should contain placeholder text."""
        template = get_default_template()
        self.assertIn("[简短标题]", template)
        self.assertIn("[类型]", template)

    def test_template_not_empty(self):
        """Template should not be empty."""
        template = get_default_template()
        self.assertGreater(len(template), 100)


if __name__ == "__main__":
    unittest.main()
