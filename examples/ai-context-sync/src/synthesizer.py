from .llm_client import LLMClient
from .profiles import LanguageProfile
from .prompt_optimizer import PromptOptimizer
from .utils import retry_on_failure


class ContextSynthesizer:
    """Uses LLM to synthesize git diffs into document updates."""

    def __init__(
        self, client: LLMClient, profile: LanguageProfile, max_retries: int = 3
    ):
        self.client = client
        self.profile = profile
        self.max_retries = max_retries
        self.optimizer = PromptOptimizer()

    @retry_on_failure(max_retries=3, delay=1.0, label="context synthesis")
    def synthesize_context_update(
        self, diff: str, commit_msg: str, current_context: str
    ) -> str:
        base_system_prompt = (
            "You are a professional project chronicler. Your task is to update the project's "
            "CONTEXT.md file based on the provided git diff and commit message. "
            "Maintain the existing structure, terminology, and tone. "
            "Only update the sections that are affected by the changes. "
            "Focus on 'Current Progress' and 'Completed Modules'. "
            "Be concise and factual. Do not add filler text. "
            "IMPORTANT: Return the FULL updated content of the file, not just the changes."
        )

        adaptive_extension = self.optimizer.optimize(diff, commit_msg, self.profile)
        system_prompt = f"{base_system_prompt}\n\n{adaptive_extension}"

        prompt = (
            f"### Current CONTEXT.md\n{current_context}\n\n"
            f"### Last Commit Message\n{commit_msg}\n\n"
            f"### Git Diff\n{diff}\n\n"
            "Please provide the complete updated version of the CONTEXT.md file."
        )

        result = self.client.generate(prompt, system_prompt=system_prompt)
        if not result or len(result) <= len(current_context) * 0.5:
            return ""
        return result

    @retry_on_failure(max_retries=3, delay=1.0, label="ADR synthesis")
    def synthesize_adr(self, diff: str, commit_msg: str) -> str:
        system_prompt = (
            "You are a software architect. Based on the code changes and commit message, "
            "draft a professional ADR following the standard format: "
            "Title, Status, Context, Decision, Consequences."
        )

        system_prompt += f"\n\n**Technical Context:** This is a {self.profile.name} project. Please use appropriate terminology."

        prompt = (
            f"Commit Message: {commit_msg}\n"
            f"Changes:\n{diff}\n\n"
            "Please draft a comprehensive ADR for this architectural change."
        )

        result = self.client.generate(prompt, system_prompt=system_prompt)
        if not result or len(result) <= 50:
            return ""
        return result
