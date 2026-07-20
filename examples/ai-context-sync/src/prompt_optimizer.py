from .profiles import LanguageProfile


class PromptOptimizer:
    """
    Dynamically adjusts the LLM's system prompt based on project scale,
    change complexity, and task type.
    """
    def __init__(self) -> None:
        # Define different strategy levels for synthesis
        self.strategies = {
            "granular": "Focus on the specific line-by-line changes. Provide high detail for every modified function and variable.",
            "balanced": "Balance between high-level intent and technical detail. Summarize the 'what' and 'why' for each module.",
            "abstract": "Focus on the architectural impact and high-level goals. Group related changes into conceptual themes and ignore minor implementation details."
        }

    def _detect_task_type(self, commit_msg: str) -> str:
        """Detects the type of task based on conventional commit prefixes."""
        msg = commit_msg.lower()
        if "feat" in msg:
            return "Feature"
        if "fix" in msg:
            return "Bugfix"
        if "refactor" in msg:
            return "Refactor"
        if "docs" in msg:
            return "Documentation"
        return "General"

    def _calculate_complexity(self, diff: str) -> str:
        """Calculates complexity based on diff size and number of files."""
        lines = diff.splitlines()
        num_files = diff.count("diff --git")

        if len(lines) < 50 or num_files <= 2:
            return "granular"
        elif len(lines) < 300 or num_files <= 10:
            return "balanced"
        else:
            return "abstract"

    def optimize(self, diff: str, commit_msg: str, profile: LanguageProfile) -> str:
        """
        Generates a tailored system prompt extension.
        """
        complexity = self._calculate_complexity(diff)
        task_type = self._detect_task_type(commit_msg)
        strategy_text = self.strategies.get(complexity, self.strategies["balanced"])

        # Construct the dynamic extension
        extension = (
            f"**Project Context:** This is a {profile.name} project. {profile.recommended_prompt_extension}\n\n"
            f"**Current Task Type:** {task_type}. {self._get_task_guideline(task_type)}\n\n"
            f"**Synthesis Strategy:** {complexity.capitalize()}. {strategy_text}"
        )
        return extension

    def _get_task_guideline(self, task_type: str) -> str:
        guidelines = {
            "Feature": "Emphasize the new capabilities added and how they integrate with existing modules.",
            "Bugfix": "Focus on the root cause of the bug and how the fix resolves it without introducing regressions.",
            "Refactor": "Highlight the improvement in code quality, performance, or maintainability, and ensure no behavioral changes.",
            "Documentation": "Focus on the clarity and completeness of the added information.",
            "General": "Provide a balanced summary of the changes."
        }
        return guidelines.get(task_type, guidelines["General"])

# Test optimizer
if __name__ == "__main__":
    from .profiles import LanguageProfile
    prof = LanguageProfile("Python", [], "Be Pythonic.")
    opt = PromptOptimizer()
    print(opt.optimize("diff... a lot of lines...", "feat: add auth", prof))
