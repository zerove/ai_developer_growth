"""Tests for pattern_learner.py (0% → 100%)."""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.pattern_learner import PatternLearner, run_pattern_learning


class TestPatternLearner:
    """Cover all paths in pattern_learner.py."""

    def test_learn_from_directory_returns_list(self):
        """learn_from_directory returns a non-None list."""
        learner = PatternLearner()
        result = learner.learn_from_directory(Path("."))
        assert isinstance(result, list)

    def test_learn_from_directory_stub_returns_default(self):
        """Learner returns the stub result with 'new_pattern'."""
        learner = PatternLearner()
        result = learner.learn_from_directory(Path("."))
        assert len(result) == 1
        assert result[0]["pattern"] == "new_pattern"
        assert "潜在" in result[0]["message"]

    def test_learn_from_directory_nonexistent_path(self):
        """Learner handles nonexistent paths (gracefully)."""
        learner = PatternLearner()
        result = learner.learn_from_directory(Path("/nonexistent/path"))
        assert isinstance(result, list)

    def test_run_pattern_learning_runs(self, capsys):
        """run_pattern_learning prints the correct message."""
        run_pattern_learning(Path("."))
        captured = capsys.readouterr()
        assert "AI 学习完成" in captured.out

    def test_run_pattern_learning_empty_result(self, capsys):
        """run_pattern_learning works with any path."""
        run_pattern_learning(Path("/tmp"))
        captured = capsys.readouterr()
        assert "AI 学习完成" in captured.out
