"""Tests for prompt optimizer"""

import tempfile

import pytest
from optimizer import PromptOptimizer, PromptVersion


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def optimizer(temp_dir):
    """Create a PromptOptimizer instance"""
    return PromptOptimizer(prompts_dir=temp_dir)


class TestPromptOptimizer:
    """Test cases for PromptOptimizer"""

    def test_save_and_load_prompt(self, optimizer):
        """Test saving and loading a prompt"""
        prompt = PromptVersion(version="1.0.0", template="Test template", model="gpt-4", score=8.0)

        optimizer.save_prompt("test-prompt", prompt)
        loaded = optimizer.load_prompt("test-prompt", "1.0.0")

        assert loaded is not None
        assert loaded.version == "1.0.0"
        assert loaded.template == "Test template"
        assert loaded.model == "gpt-4"
        assert loaded.score == 8.0

    def test_list_versions(self, optimizer):
        """Test listing all versions"""
        # Save multiple versions
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            prompt = PromptVersion(version=v, template=f"Template {v}")
            optimizer.save_prompt("test-prompt", prompt)

        versions = optimizer.list_versions("test-prompt")

        assert len(versions) == 3
        assert "1.0.0" in versions
        assert "1.1.0" in versions
        assert "2.0.0" in versions

    def test_compare_versions(self, optimizer):
        """Test comparing two versions"""
        # Save two versions with different scores
        prompt1 = PromptVersion(version="1.0.0", template="v1", score=7.0)
        prompt2 = PromptVersion(version="2.0.0", template="v2", score=8.5)

        optimizer.save_prompt("test-prompt", prompt1)
        optimizer.save_prompt("test-prompt", prompt2)

        result = optimizer.compare_versions("test-prompt", "1.0.0", "2.0.0")

        assert result["version1"]["score"] == 7.0
        assert result["version2"]["score"] == 8.5
        assert result["score_diff"] == 1.5
        assert result["improvement"] is True

    def test_generate_suggestions(self, optimizer):
        """Test generating optimization suggestions"""
        prompt = PromptVersion(
            version="1.0.0",
            template="Short template",
            score=5.0,  # Low score
            metadata={},  # Missing examples and constraints
        )

        optimizer.save_prompt("test-prompt", prompt)
        suggestions = optimizer.generate_optimization_suggestions("test-prompt", "1.0.0")

        assert len(suggestions) > 0
        assert any("分数较低" in s for s in suggestions)
        assert any("示例" in s for s in suggestions)
        assert any("约束条件" in s for s in suggestions)

    def test_load_nonexistent_prompt(self, optimizer):
        """Test loading a non-existent prompt"""
        loaded = optimizer.load_prompt("nonexistent", "1.0.0")
        assert loaded is None

    def test_compare_nonexistent_versions(self, optimizer):
        """Test comparing non-existent versions"""
        result = optimizer.compare_versions("nonexistent", "1.0.0", "2.0.0")
        assert "error" in result
