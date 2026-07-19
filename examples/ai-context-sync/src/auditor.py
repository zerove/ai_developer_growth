import json
import os
from dataclasses import dataclass
from typing import Any, List, Optional

from .exceptions import LLMError
from .llm_client import LLMClient
from .logger import logger
from .utils import parse_llm_json


@dataclass
class Violation:
    """Represents a single specification violation."""
    rule_id: str
    message: str
    severity: str  # 'Critical', 'Warning', 'Info'
    file_path: str
    line_number: Optional[int] = None
    status: str = "open"  # 'open', 'fixed', 'overridden'

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__

class FeedbackManager:
    """
    Tracks the history of specification violations and developer feedback.
    """
    def __init__(self, history_file: str = ".ai-audit-history.json"):
        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self) -> List[dict]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def save_violation(self, violation: Violation) -> None:
        """Records a new violation in the history."""
        for item in self.history:
            if (item['rule_id'] == violation.rule_id and
                item['file_path'] == violation.file_path and
                item['message'] == violation.message):
                return

        self.history.append(violation.to_dict())
        self._persist()

    def update_status(self, rule_id: str, status: str) -> None:
        """Updates the status of all violations for a specific rule."""
        for item in self.history:
            if item['rule_id'] == rule_id:
                item['status'] = status
        self._persist()

    def _persist(self) -> None:
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

class SpecAuditor:
    """
    Audits code against language-specific development specifications.
    Implements an Adversarial Audit (Attack -> Verify) loop to minimize false positives.
    """
    def __init__(self, llm_client: LLMClient, specs_dir: str):
        self.llm_client = llm_client
        self.specs_dir = specs_dir

    def get_relevant_specs(self, diff: str) -> str:
        all_specs = ""
        if os.path.exists(self.specs_dir):
            for file in os.listdir(self.specs_dir):
                if file.endswith(".md"):
                    with open(os.path.join(self.specs_dir, file), "r", encoding="utf-8") as f:
                        all_specs += f"\n--- Spec: {file} ---\n{f.read()}\n"
        return all_specs

    def _verify_violation(self, violation: Violation, diff: str, spec_text: str) -> bool:
        """
        The Verifier Agent checks if a candidate violation is actually a violation.
        """
        system_prompt = (
            "You are a neutral, high-level software architect. Your task is to verify if a "
            "reported specification violation is actually a violation or a false positive. "
            "Be rigorous and objective. If the code actually follows the spirit of the spec, "
            "or if the reported violation is a hallucination, mark it as a false positive."
        )

        prompt = (
            f"Spec Rule: {spec_text}\n\n"
            f"Code Diff: {diff}\n\n"
            f"Reported Violation: {violation.message} (Rule: {violation.rule_id})\n\n"
            "Is this a real violation? Reply only with 'YES' or 'NO' followed by a brief explanation."
        )

        try:
            response = self.llm_client.generate(prompt, system_prompt=system_prompt)
            return bool(response and response.strip().upper().startswith("YES"))
        except LLMError as e:
            logger.error(f"Error during verification: {e}")
            return False

    def generate_fix(self, violation: Violation, diff: str, spec_text: str) -> str:
        """
        Generates a suggested fix for a specific violation.
        """
        system_prompt = (
            "You are a pragmatic senior developer. Your task to fix a specific specification violation "
            "in the provided code. Ensure the fix is minimal, correct, and strictly follows the project spec."
        )

        prompt = (
            f"Spec Rule: {spec_text}\n\n"
            f"Code Diff: {diff}\n\n"
            f"Violation: {violation.message} (Rule: {violation.rule_id})\n\n"
            "Please provide the corrected version of the affected code. "
            "Return ONLY the corrected code block, no explanations."
        )

        try:
            response = self.llm_client.generate(prompt, system_prompt=system_prompt)
            return response if response else "Could not generate a fix."
        except LLMError as e:
            logger.error(f"Error generating fix: {e}")
            return "Error generating fix."

    def audit(self, diff: str, task: str) -> List[Violation]:
        """
        Performs an adversarial audit: Attack -> Verify.
        Returns only confirmed violations.
        """
        specs = self.get_relevant_specs(diff)
        if not specs:
            return []

        # --- Phase 1: Attack (Finding candidates) ---
        attack_system_prompt = (
            "You are a strict technical auditor. Your task is to find ALL possible violations "
            "of the project's language specifications in the provided diff. "
            "Be extremely pedantic. If you suspect a violation, report it. "
            "OUTPUT FORMAT: Return a JSON list of violations. "
            "Each object must have: 'rule_id', 'message', 'severity' ('Critical', 'Warning', 'Info'). "
            "If no violations are found, return [].\n\n"
            f"SPECIFICATIONS:\n{specs}"
        )

        attack_prompt = f"Task: {task}\n\nCode Diff:\n{diff}"

        try:
            attack_response = self.llm_client.generate(attack_prompt, system_prompt=attack_system_prompt)
            candidates_data = parse_llm_json(attack_response, label="adversarial audit")
            if not candidates_data:
                return []

            candidates = [
                Violation(
                    rule_id=v.get("rule_id", "UNKNOWN"),
                    message=v.get("message", "No message provided"),
                    severity=v.get("severity", "Info"),
                    file_path="unknown"
                ) for v in candidates_data
            ]

            confirmed_violations = [
                v for v in candidates
                if self._verify_violation(v, diff, specs)
            ]

            return confirmed_violations
        except LLMError as e:
            logger.error(f"Error during adversarial audit: {e}")
            return []
