#!/usr/bin/env python3
"""Tests for create_case_study.py"""

import tempfile
from pathlib import Path

import pytest

from tools.scripts.create_case_study import create_case_study_structure, get_default_template


class TestCreateCaseStudy:
    """Test case study creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir) / "case-studies"
        self.base_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_case_study_creates_dirs(self):
        """Test that all expected directories are created."""
        case_dir = create_case_study_structure("Test Case", self.base_dir)

        assert case_dir.exists()
        assert (case_dir / "code").is_dir()
        assert (case_dir / "docs").is_dir()
        assert (case_dir / "tests").is_dir()
        assert (case_dir / "assets").is_dir()

    def test_create_case_study_readme(self):
        """Test that README.md is created from template."""
        case_dir = create_case_study_structure("My Project", self.base_dir)

        readme = case_dir / "README.md"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert "My Project" in content
        assert "案例" in content

    def test_create_case_study_doc_files(self):
        """Test that PRD.md, DESIGN.md, RETROSPECTIVE.md are created."""
        case_dir = create_case_study_structure("Test Case", self.base_dir)

        docs_dir = case_dir / "docs"
        assert (docs_dir / "PRD.md").exists()
        assert (docs_dir / "DESIGN.md").exists()
        assert (docs_dir / "RETROSPECTIVE.md").exists()

    def test_create_case_study_gitkeep(self):
        """Test that .gitkeep files are created."""
        case_dir = create_case_study_structure("Test Case", self.base_dir)

        assert (case_dir / "code" / ".gitkeep").exists()
        assert (case_dir / "tests" / ".gitkeep").exists()
        assert (case_dir / "assets" / ".gitkeep").exists()

    def test_create_case_study_name_sanitization(self):
        """Test that name is lowercased and spaces become hyphens."""
        case_dir = create_case_study_structure("My Great Project", self.base_dir)

        assert case_dir.name == "my-great-project"

    def test_create_case_study_idempotent(self):
        """Test that creating the same case study twice doesn't error."""
        case_dir1 = create_case_study_structure("Test", self.base_dir)
        case_dir2 = create_case_study_structure("Test", self.base_dir)

        assert case_dir1 == case_dir2
        assert (case_dir1 / "README.md").exists()

    def test_get_default_template(self):
        """Test that default template has expected sections."""
        template = get_default_template()

        assert "案例" in template
        assert "效率对比" in template
        assert "关键洞察" in template
        assert "适用场景" in template
        assert "交付物清单" in template
        assert "提交前检查" in template
        assert "[简短标题" in template

    def test_create_case_study_with_template(self):
        """Test creating case study when template file exists."""
        # Create a template file
        template_dir = self.base_dir.parent / "templates"
        template_dir.mkdir(exist_ok=True)
        (template_dir / "case-study-template.md").write_text(
            "# Custom Template: [简短标题]\n", encoding="utf-8"
        )

        case_dir = create_case_study_structure("Custom", self.base_dir)
        readme = case_dir / "README.md"
        content = readme.read_text(encoding="utf-8")
        assert "Custom" in content

    def test_create_case_study_existing_docs_not_overwritten(self):
        """Test that existing doc files are not overwritten."""
        case_dir = create_case_study_structure("Test", self.base_dir)
        prd_path = case_dir / "docs" / "PRD.md"
        prd_path.write_text("# Custom PRD\n", encoding="utf-8")

        # Re-create - should not overwrite
        create_case_study_structure("Test", self.base_dir)
        content = prd_path.read_text(encoding="utf-8")
        assert content == "# Custom PRD\n"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
