"""Tests for src/prompt_optimizer.py - PromptOptimizer"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.profiles import LanguageProfile
from src.prompt_optimizer import PromptOptimizer


def _make_profile(name="Python", prompt_ext="Be Pythonic."):
    return LanguageProfile(name=name, default_ignore=[], recommended_prompt_extension=prompt_ext)


class TestDetectTaskType:
    def setup_method(self):
        self.optimizer = PromptOptimizer()

    def test_feature_commit(self):
        assert self.optimizer._detect_task_type("feat: add user auth") == "Feature"

    def test_fix_commit(self):
        assert self.optimizer._detect_task_type("fix: resolve null pointer") == "Bugfix"

    def test_refactor_commit(self):
        assert self.optimizer._detect_task_type("refactor: extract service layer") == "Refactor"

    def test_docs_commit(self):
        assert self.optimizer._detect_task_type("docs: update README") == "Documentation"

    def test_general_commit(self):
        assert self.optimizer._detect_task_type("chore: clean up") == "General"

    def test_case_insensitive(self):
        assert self.optimizer._detect_task_type("FEAT: uppercase") == "Feature"
        assert self.optimizer._detect_task_type("FIX: mixed") == "Bugfix"

    def test_keyword_in_middle_of_message(self):
        assert self.optimizer._detect_task_type("WIP: working on feat") == "Feature"

    def test_empty_string(self):
        assert self.optimizer._detect_task_type("") == "General"

    def test_feat_before_fix(self):
        """'feat' appears before 'fix' so Feature should win."""
        assert self.optimizer._detect_task_type("feat: fix something") == "Feature"

    def test_multiple_keywords_feat_wins(self):
        assert self.optimizer._detect_task_type("feat: refactor and fix bugs") == "Feature"


class TestCalculateComplexity:
    def setup_method(self):
        self.optimizer = PromptOptimizer()

    def test_empty_diff_returns_granular(self):
        assert self.optimizer._calculate_complexity("") == "granular"

    def test_short_diff_returns_granular(self):
        diff = "line1\nline2\nline3\nline4"
        assert self.optimizer._calculate_complexity(diff) == "granular"

    def test_exactly_50_lines_with_few_files_returns_balanced(self):
        """>=50 lines but <=2 files triggers the balanced branch."""
        lines = ["diff --git a/f1 b/f1"] + ["+" + str(i) for i in range(50)]
        diff = "\n".join(lines)
        assert self.optimizer._calculate_complexity(diff) == "balanced"

    def test_few_lines_many_files_returns_granular(self):
        """<50 lines but >2 files still returns granular (line check comes first)."""
        lines = ["diff --git a/f1 b/f1", "diff --git a/f2 b/f2", "diff --git a/f3 b/f3"]
        lines += ["+" + str(i) for i in range(10)]
        diff = "\n".join(lines)
        assert self.optimizer._calculate_complexity(diff) == "granular"

    def test_medium_diff_returns_balanced(self):
        lines = ["diff --git a/f1 b/f1"] * 5
        lines += ["+" + str(i) for i in range(100)]
        diff = "\n".join(lines)
        assert self.optimizer._calculate_complexity(diff) == "balanced"

    def test_large_diff_returns_abstract(self):
        lines = ["diff --git a/f{} b/f{}".format(i, i) for i in range(15)]
        lines += ["+" + str(i) for i in range(400)]
        diff = "\n".join(lines)
        assert self.optimizer._calculate_complexity(diff) == "abstract"

    def test_boundary_300_lines_with_few_files(self):
        """Exactly 300 lines + <=2 files => balanced (300 is not < 300)."""
        lines = ["diff --git a/f1 b/f1"]
        lines += ["+" + str(i) for i in range(299)]
        diff = "\n".join(lines)
        assert self.optimizer._calculate_complexity(diff) == "balanced"

    def test_301_lines_with_few_files_returns_abstract(self):
        lines = ["diff --git a/f1 b/f1"]
        lines += ["+" + str(i) for i in range(300)]
        diff = "\n".join(lines)
        assert self.optimizer._calculate_complexity(diff) == "abstract"


class TestOptimize:
    def setup_method(self):
        self.optimizer = PromptOptimizer()

    def test_returns_string(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "feat: x", profile)
        assert isinstance(result, str)

    def test_contains_project_context(self):
        profile = _make_profile(name="Rust", prompt_ext="Focus on ownership.")
        result = self.optimizer.optimize("diff", "feat: x", profile)
        assert "Rust" in result
        assert "Focus on ownership." in result

    def test_contains_task_type(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "feat: add login", profile)
        assert "Feature" in result

    def test_contains_strategy_label(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "feat: x", profile)
        assert any(s in result.lower() for s in ("granular", "balanced", "abstract"))

    def test_feature_guideline(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "feat: new endpoint", profile)
        assert "new capabilities" in result.lower() or "emphasize" in result.lower()

    def test_bugfix_guideline(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "fix: memory leak", profile)
        assert "root cause" in result.lower()

    def test_refactor_guideline(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "refactor: clean up", profile)
        assert "code quality" in result.lower() or "improvement" in result.lower()

    def test_docs_guideline(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "docs: add examples", profile)
        assert "clarity" in result.lower() or "completeness" in result.lower()

    def test_general_guideline(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "chore: misc", profile)
        assert "balanced summary" in result.lower()

    def test_short_diff_granular_strategy(self):
        profile = _make_profile()
        result = self.optimizer.optimize("short diff", "feat: x", profile)
        assert "Granular" in result

    def test_long_diff_abstract_strategy(self):
        profile = _make_profile()
        long_diff = "diff --git a/f{} b/f{}\n".format(0, 0) * 15 + "x\n" * 400
        result = self.optimizer.optimize(long_diff, "feat: x", profile)
        assert "Abstract" in result

    def test_empty_diff(self):
        profile = _make_profile()
        result = self.optimizer.optimize("", "feat: x", profile)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_commit_message(self):
        profile = _make_profile()
        result = self.optimizer.optimize("diff", "", profile)
        assert "General" in result

    def test_generic_profile(self):
        profile = _make_profile(name="Generic", prompt_ext="Standard summary.")
        result = self.optimizer.optimize("diff", "feat: x", profile)
        assert "Generic" in result
        assert "Standard summary." in result


class TestTaskGuidelines:
    """Verify every task type maps to a non-empty guideline."""

    def setup_method(self):
        self.optimizer = PromptOptimizer()

    def test_all_task_types_have_guidelines(self):
        task_types = ["Feature", "Bugfix", "Refactor", "Documentation", "General"]
        for tt in task_types:
            guideline = self.optimizer._get_task_guideline(tt)
            assert isinstance(guideline, str)
            assert len(guideline) > 10, f"Task type '{tt}' has a short/empty guideline"

    def test_unknown_task_type_returns_general_guideline(self):
        # _get_task_guideline falls back to General for unknown keys
        guideline = self.optimizer._get_task_guideline("NonexistentTask")
        assert "balanced summary" in guideline.lower()
