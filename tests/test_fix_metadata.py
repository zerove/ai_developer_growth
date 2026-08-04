import os
import shutil
import tempfile
import unittest

from tools.scripts.fix_metadata import (
    DIR_CATEGORY_MAP,
    generate_metadata,
    get_category_from_path,
    infer_difficulty,
    infer_tags,
    infer_title_from_content,
    process_file,
)


class TestGetCategoryFromPath(unittest.TestCase):
    """Test category inference from file path."""

    def test_docs_efficiency(self):
        """Should map docs/efficiency to 效率层."""
        cat, tags = get_category_from_path("docs/efficiency/test.md")
        self.assertEqual(cat, "效率层")
        self.assertIn("AI效率", tags)

    def test_docs_mindset(self):
        """Should map docs/mindset to 心态层."""
        cat, tags = get_category_from_path("docs/mindset/growth.md")
        self.assertEqual(cat, "心态层")

    def test_docs_tools(self):
        """Should map docs/tools to 工具层."""
        cat, tags = get_category_from_path("docs/tools/vim.md")
        self.assertEqual(cat, "工具层")

    def test_docs_governance(self):
        """Should map docs/governance to 治理层."""
        cat, tags = get_category_from_path("docs/governance/standards.md")
        self.assertEqual(cat, "治理层")

    def test_docs_learning(self):
        """Should map docs/learning to 学习层."""
        cat, tags = get_category_from_path("docs/learning/python.md")
        self.assertEqual(cat, "学习层")

    def test_docs_database(self):
        """Should map docs/database to 工具层."""
        cat, tags = get_category_from_path("docs/database/postgres.md")
        self.assertEqual(cat, "工具层")
        self.assertIn("数据库", tags)

    def test_docs_caching(self):
        """Should map docs/caching to 工具层."""
        cat, tags = get_category_from_path("docs/caching/redis.md")
        self.assertEqual(cat, "工具层")
        self.assertIn("缓存", tags)

    def test_docs_devops(self):
        """Should map docs/devops to 工具层."""
        cat, tags = get_category_from_path("docs/devops/docker.md")
        self.assertEqual(cat, "工具层")

    def test_docs_security(self):
        """Should map docs/security to 治理层."""
        cat, tags = get_category_from_path("docs/security/auth.md")
        self.assertEqual(cat, "治理层")

    def test_docs_testing(self):
        """Should map docs/testing to 工具层."""
        cat, tags = get_category_from_path("docs/testing/pytest.md")
        self.assertEqual(cat, "工具层")

    def test_unknown_path_defaults(self):
        """Unknown paths should default to 效率层."""
        cat, tags = get_category_from_path("unknown/path/file.md")
        self.assertEqual(cat, "效率层")

    def test_docs_frameworks(self):
        """Should map docs/frameworks to 工具层."""
        cat, tags = get_category_from_path("docs/frameworks/fastapi.md")
        self.assertEqual(cat, "工具层")

    def test_docs_monitoring(self):
        """Should map docs/monitoring to 工具层."""
        cat, tags = get_category_from_path("docs/monitoring/prometheus.md")
        self.assertEqual(cat, "工具层")

    def test_docs_message_queue(self):
        """Should map docs/message-queue to 工具层."""
        cat, tags = get_category_from_path("docs/message-queue/kafka.md")
        self.assertEqual(cat, "工具层")
        self.assertIn("消息队列", tags)

    def test_docs_integration(self):
        """Should map docs/integration to 工具层."""
        cat, tags = get_category_from_path("docs/integration/webhook.md")
        self.assertEqual(cat, "工具层")

    def test_docs_specs(self):
        """Should map docs/specs to 治理层."""
        cat, tags = get_category_from_path("docs/specs/api-spec.md")
        self.assertEqual(cat, "治理层")

    def test_docs_specialization(self):
        """Should map docs/specialization to 学习层."""
        cat, tags = get_category_from_path("docs/specialization/ml.md")
        self.assertEqual(cat, "学习层")

    def test_docs_api(self):
        """Should map docs/api to 工具层."""
        cat, tags = get_category_from_path("docs/api/rest.md")
        self.assertEqual(cat, "工具层")

    def test_docs_agent_dev(self):
        """Should map docs/agent-dev to 治理层."""
        cat, tags = get_category_from_path("docs/agent-dev/agents.md")
        self.assertEqual(cat, "治理层")

    def test_docs_adr(self):
        """Should map docs/adr to 治理层."""
        cat, tags = get_category_from_path("docs/adr/adr-001.md")
        self.assertEqual(cat, "治理层")

    def test_docs_moc(self):
        """Should map docs/moc to 治理层."""
        cat, tags = get_category_from_path("docs/moc/index.md")
        self.assertEqual(cat, "治理层")

    def test_all_dirs_mapped(self):
        """All DIR_CATEGORY_MAP entries should be testable."""
        for dir_path in DIR_CATEGORY_MAP:
            cat, tags = get_category_from_path(f"{dir_path}/file.md")
            self.assertIsNotNone(cat)
            self.assertIsInstance(tags, list)


class TestInferTitle(unittest.TestCase):
    """Test title inference from content."""

    def test_from_heading(self):
        """Should extract title from first H1 heading."""
        content = "# My Title\n\nSome content"
        title = infer_title_from_content(content, "test.md")
        self.assertEqual(title, "My Title")

    def test_from_filename(self):
        """Should infer title from filename when no heading."""
        content = "Some content without heading"
        title = infer_title_from_content(content, "my-test-file.md")
        title_str = title if isinstance(title, str) else str(title)
        self.assertIn("My", title_str)

    def test_from_heading_with_chinese(self):
        """Should extract Chinese heading."""
        content = "# Python 学习笔记\n\n内容"
        title = infer_title_from_content(content, "test.md")
        self.assertEqual(title, "Python 学习笔记")

    def test_heading_with_extra_spaces(self):
        """Should handle extra spaces in heading."""
        content = "#   Spaced Title   \n\nContent"
        title = infer_title_from_content(content, "test.md")
        self.assertEqual(title, "Spaced Title")


class TestInferDifficulty(unittest.TestCase):
    """Test difficulty inference."""

    def test_advanced(self):
        """Should detect advanced content."""
        content = "This is an advanced topic about complex systems"
        diff = infer_difficulty(content)
        self.assertEqual(diff, "高级")

    def test_intermediate(self):
        """Should detect intermediate content."""
        content = "This is an intermediate level tutorial"
        diff = infer_difficulty(content)
        self.assertEqual(diff, "中级")

    def test_beginner_default(self):
        """Should default to beginner level."""
        content = "Simple introduction to basics"
        diff = infer_difficulty(content)
        self.assertEqual(diff, "初级")

    def test_advanced_english(self):
        """Should detect English advanced keywords."""
        content = "Expert level configuration guide"
        diff = infer_difficulty(content)
        self.assertEqual(diff, "高级")

    def test_intermediate_english(self):
        """Should detect English intermediate keywords."""
        content = "Intermediate configuration guide"
        diff = infer_difficulty(content)
        self.assertEqual(diff, "中级")


class TestInferTags(unittest.TestCase):
    """Test tag inference."""

    def test_from_filename(self):
        """Should extract tags from hyphenated filename."""
        tags = infer_tags("Python content", "ai-llm-gpt.md")
        self.assertIsInstance(tags, list)
        self.assertGreater(len(tags), 0)

    def test_from_content_python(self):
        """Should detect Python keyword."""
        tags = infer_tags("This uses python for coding", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("Python", tag_str)

    def test_from_content_docker(self):
        """Should detect Docker keyword."""
        tags = infer_tags("Using docker containers", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("Docker", tag_str)

    def test_from_content_ai(self):
        """Should detect AI keyword."""
        tags = infer_tags("AI and LLM applications", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("AI", tag_str)

    def test_max_5_tags(self):
        """Should return at most 5 tags."""
        tags = infer_tags(
            "python javascript typescript react vue angular docker kubernetes ai llm gpt api rest graphql database sql",
            "test.md",
        )
        self.assertLessEqual(len(tags), 5)

    def test_default_tag(self):
        """Should return default tag when no keywords found."""
        tags = infer_tags("Some random text", "xyz.md")
        self.assertIn("技术文档", tags)

    def test_from_content_javascript(self):
        """Should detect JavaScript keyword."""
        tags = infer_tags("Using javascript frameworks", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("JavaScript", tag_str)

    def test_from_content_typescript(self):
        """Should detect TypeScript keyword."""
        tags = infer_tags("Using typescript for type safety", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("TypeScript", tag_str)

    def test_from_content_react(self):
        """Should detect React keyword."""
        tags = infer_tags("Using react components", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("React", tag_str)

    def test_from_content_kubernetes(self):
        """Should detect Kubernetes keyword."""
        tags = infer_tags("Using kubernetes for deployment", "test.md")
        tag_str = " ".join(tags)
        self.assertIn("Kubernetes", tag_str)


class TestGenerateMetadata(unittest.TestCase):
    """Test metadata generation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generates_valid_frontmatter(self):
        """Should generate valid YAML frontmatter."""
        test_file = os.path.join(self.test_dir, "test.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Test Title\n\nSome content about Python")

        metadata = generate_metadata(test_file)
        self.assertIn("---", metadata)
        self.assertIn("title:", metadata)
        self.assertIn("description:", metadata)
        self.assertIn("category:", metadata)
        self.assertIn("tags:", metadata)
        self.assertIn("difficulty:", metadata)
        self.assertIn("reading_time:", metadata)
        self.assertIn("updated:", metadata)

    def test_metadata_ends_with_newlines(self):
        """Generated metadata should have trailing newlines for proper concatenation."""
        test_file = os.path.join(self.test_dir, "test.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Title\n\nBody")

        metadata = generate_metadata(test_file)
        self.assertTrue(metadata.endswith("\n\n") or metadata.endswith("\n---\n\n"))

    def test_generates_for_different_dirs(self):
        """Should generate appropriate metadata for different directories."""
        for dir_name in ["mindset", "learning", "efficiency", "tools", "governance"]:
            test_file = os.path.join(self.test_dir, f"{dir_name}.md")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# Test\n\nContent")
            metadata = generate_metadata(test_file)
            self.assertIn("---", metadata)


class TestProcessFile(unittest.TestCase):
    """Test file processing logic."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_add_metadata_to_file_without_frontmatter(self):
        """Should add metadata to file without frontmatter."""
        test_file = os.path.join(self.test_dir, "no-meta.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Title\n\nContent")

        result = process_file(test_file)
        self.assertTrue(result)

        with open(test_file, encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.startswith("---"))
        self.assertIn("title:", content)

    def test_skip_file_with_complete_metadata(self):
        """Should skip file with complete metadata."""
        test_file = os.path.join(self.test_dir, "complete.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""---
title: Test
description: Desc
category: 效率层
tags: ['AI']
difficulty: 中级
---

# Content""")

        result = process_file(test_file)
        self.assertFalse(result)

    def test_replace_incomplete_metadata(self):
        """Should replace incomplete metadata."""
        test_file = os.path.join(self.test_dir, "incomplete.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""---
title: Only Title
---

# Content""")

        result = process_file(test_file)
        self.assertTrue(result)

        with open(test_file, encoding="utf-8") as f:
            content = f.read()
        # Should have new metadata with all required fields
        self.assertIn("description:", content)
        self.assertIn("category:", content)

    def test_preserves_content(self):
        """Original content should be preserved after processing."""
        test_file = os.path.join(self.test_dir, "preserve.md")
        original_content = "# My Title\n\nThis is important content."
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(original_content)

        process_file(test_file)

        with open(test_file, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("This is important content.", content)
        self.assertIn("# My Title", content)


if __name__ == "__main__":
    unittest.main()
