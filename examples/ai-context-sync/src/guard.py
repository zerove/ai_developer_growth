import os
from typing import List

from .llm_client import LLMClient
from .utils import parse_llm_json


class ArchitectureGuard:
    """
    Ensures that code changes align with established Architecture Decision Records (ADRs).
    """

    def __init__(self, client: LLMClient, adr_dir: str):
        self.client = client
        self.adr_dir = adr_dir

    def _load_adrs(self) -> str:
        """
        Loads all ADR files into a single string for the LLM.
        """
        if not os.path.exists(self.adr_dir):
            return "No ADRs defined yet."

        adr_contents = []
        for filename in sorted(os.listdir(self.adr_dir)):
            if filename.endswith(".md"):
                with open(
                    os.path.join(self.adr_dir, filename), "r", encoding="utf-8"
                ) as f:
                    adr_contents.append(f"--- File: {filename} ---\n{f.read()}")

        return "\n\n".join(adr_contents) if adr_contents else "No ADRs defined yet."

    def check_design_drift(self, design_doc: str, task: str) -> str:
        """
        Analyzes a proposed technical design against ADRs to detect potential architectural drift
        before implementation begins.
        """
        adrs = self._load_adrs()
        if adrs == "No ADRs defined yet.":
            return "✅ No ADRs found. Design is technically compliant."

        system_prompt = (
            "You are a strict Software Architecture Auditor. Your goal is to ensure that "
            "a proposed technical design does not violate established Architecture Decision Records (ADRs). "
            "Analyze the provided ADRs and the proposed design. "
            "If the design contradicts a decision, mark it as a 'VIOLATION'. "
            "If it aligns or is unrelated, mark it as 'COMPLIANT'. "
            "Be precise, cite the specific ADR file, and explain the conflict."
        )

        prompt = (
            f"### Established ADRs\n{adrs}\n\n"
            f"### Proposed Task: {task}\n"
            f"### Proposed Technical Design:\n{design_doc}\n\n"
            "Please provide a 'Design Drift Report'. If the design is compliant, simply say 'All design aspects are compliant'."
        )

        return (
            self.client.generate(prompt, system_prompt=system_prompt)
            or "Error: LLM failed to generate design drift report."
        )

    def check_drift_json(self, diff: str, commit_msg: str) -> List[dict]:
        """
        Compares current changes against ADRs and returns structured violations.
        """
        adrs = self._load_adrs()
        if adrs == "No ADRs defined yet.":
            return []

        system_prompt = (
            "You are a strict Software Architecture Auditor. "
            "Analyze the provided ADRs and the Git Diff. "
            "Return ONLY a JSON array of objects with keys: "
            "'rule_id', 'adr_file', 'severity', 'description'. "
            "If no violations, return an empty array []."
        )

        prompt = (
            f"### Established ADRs\n{adrs}\n\n"
            f"### Current Commit Message\n{commit_msg}\n\n"
            f"### Git Diff\n{diff}\n\n"
            "Violations (JSON array):"
        )

        response = self.client.generate(prompt, system_prompt=system_prompt)
        result = parse_llm_json(response, label="architecture guard")
        return result if result is not None else []


# Test guard
if __name__ == "__main__":
    from .llm_client import LLMClient

    client = LLMClient()
    guard = ArchitectureGuard(client, "docs/adr/")
    print(guard.check_design_drift("diff... ", "feat: use sqlite"))
