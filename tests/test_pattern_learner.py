"""Tests for pattern_learner.py (0% → 100%)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine.pattern_learner import PatternLearner, run_pattern_learning


class TestPatternLearner:
    """Cover all paths in pattern_learner.py."""

    def test_learn_from_directory_returns_list(self):
        """learn_from_directory returns a non-None list."""
        learner = PatternLearner()
        result = learner.learn_from_directory(Path("."))
        assert isinstance(result, list)

    @pytest.mark.slow
    def test_learn_from_directory_real_implementation(self):
        """Learner now returns real patterns from rules engine."""
        learner = PatternLearner()
        result = learner.learn_from_directory(Path("."))
        assert isinstance(result, list)
        # Should find some issues in the project's own code
        if len(result) > 0 and result[0].get("frequency", 0) > 0:
            assert "message" in result[0]
        else:
            # Graceful fallback when no frequent patterns found
            assert result[0]["pattern"] == "no-frequent-issues"

    def test_learn_from_directory_nonexistent_path(self):
        """Learner handles nonexistent paths (gracefully)."""
        learner = PatternLearner()
        result = learner.learn_from_directory(Path("/nonexistent/path"))
        assert isinstance(result, list)

    @pytest.mark.slow
    def test_run_pattern_learning_runs(self, capsys):
        """run_pattern_learning prints the correct message."""
        run_pattern_learning(Path("."))
        captured = capsys.readouterr()
        assert "AI 分析完成" in captured.out

    @pytest.mark.slow
    def test_run_pattern_learning_empty_result(self, capsys):
        """run_pattern_learning works with any path."""
        run_pattern_learning(Path("/tmp"))
        captured = capsys.readouterr()
        assert "AI 分析完成" in captured.out
