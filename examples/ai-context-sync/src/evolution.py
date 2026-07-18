import os
import json
from typing import Any, Dict, List, Optional
from .llm_client import LLMClient
from .auditor import FeedbackManager

class EvolutionEngine:
    """
    Analyzes audit history to detect patterns of specification overrides
    and proposes updates to the project's specifications.
    """
    def __init__(self, llm_client: LLMClient, feedback_manager: FeedbackManager, specs_dir: str):
        self.llm_client = llm_client
        self.feedback_manager = feedback_manager
        self.specs_dir = specs_dir
        self.conflict_threshold = 0.6  # If >60% of occurrences are overridden, suggest evolution

    def analyze_conflicts(self) -> List[Dict]:
        """
        Analyzes the history to find rules that are frequently overridden.
        """
        history = self.feedback_manager.history
        if not history:
            return []

        # Count total vs overridden occurrences per rule_id
        stats: Dict[str, Dict[str, Any]] = {}
        for item in history:
            rid = item['rule_id']
            if rid not in stats:
                stats[rid] = {"total": 0, "overridden": 0, "examples": []}
            
            stats[rid]["total"] += 1
            if item['status'] == 'overridden':
                stats[rid]["overridden"] += 1
                # Store a few examples of the violation for the LLM to analyze
                if len(stats[rid]["examples"]) < 3:
                    stats[rid]["examples"].append({
                        "message": item['message'],
                        "file": item['file_path']
                    })

        # Identify candidates for evolution
        candidates = []
        for rid, data in stats.items():
            ratio = data["overridden"] / data["total"]
            if ratio >= self.conflict_threshold and data["total"] >= 2:
                candidates.append({
                    "rule_id": rid,
                    "ratio": ratio,
                    "total": data["total"],
                    "overridden": data["overridden"],
                    "examples": data["examples"]
                })
        
        return candidates

    def propose_evolution(self, candidate: Dict) -> Optional[str]:
        """
        Uses the LLM to propose a structured evolution of a specification rule.
        """
        rid = candidate["rule_id"]
        examples = candidate["examples"]
        
        # Find the current spec content
        current_spec = self._find_spec_content(rid)
        
        system_prompt = (
            "You are a senior software architect and standards engineer. "
            "Your task is to evolve a project's coding specification based on observed developer preferences. "
            "The developer has consistently overridden a specific rule, suggesting the current rule is "
            "too strict, outdated, or doesn't fit the project's unique context."
        )
        
        prompt = (
            f"Rule ID: {rid}\n"
            f"Current Specification: {current_spec}\n\n"
            f"Observed Override Patterns (Example Violations):\n"
            f"{json.dumps(examples, indent=2)}\n\n"
            "Please provide a structured evolution proposal including:\n"
            "1. RATIONALE: Why the current rule is causing friction and why the change is justified.\n"
            "2. PROPOSED RULE: The updated, precise wording of the rule.\n"
            "3. IMPACT: How this change affects the overall codebase quality.\n\n"
            "Return the response in a clear, professional format."
        )
        
        return self.llm_client.generate(prompt, system_prompt=system_prompt)

    def propose_batch_evolution(self, candidates: List[Dict]) -> Optional[str]:
        """
        Analyzes all candidates together to propose a consistent update to the specifications.
        """
        if not candidates:
            return "No candidates found for batch evolution."

        # Gather all relevant specs
        specs_info = []
        for c in candidates:
            content = self._find_spec_content(c["rule_id"])
            specs_info.append(f"Rule {c['rule_id']}:\n{content}\nExamples: {json.dumps(c['examples'])}")

        system_prompt = (
            "You are a senior software architect. You are reviewing a set of project specifications "
            "that are frequently overridden by developers. Your goal is to propose a consistent, "
            "holistic update to these rules to align them with actual project practice while "
            "maintaining high quality standards."
        )
        
        newline = '\n'
        prompt = (
            f"The following rules are under review for evolution:\n\n"
            f"{'---' * 10}\n"
            f"{newline.join(specs_info)}\n"
            f"{'---' * 10}\n\n"
            "Please provide a batch evolution report. For each rule, provide a rationale and the updated wording. "
            "Ensure that the updated rules are consistent with each other. "
            "Structure your response as a formal specification update document."
        )
        
        return self.llm_client.generate(prompt, system_prompt=system_prompt)

    def _find_spec_content(self, rule_id: str) -> str:
        """Searches through spec files to find the current text for a rule_id."""
        if not os.path.exists(self.specs_dir):
            return "No specification found."
            
        for file in os.listdir(self.specs_dir):
            if file.endswith(".md"):
                with open(os.path.join(self.specs_dir, file), "r", encoding="utf-8") as f:
                    content = f.read()
                    if rule_id in content:
                        # Return the paragraph containing the rule_id
                        paragraphs = content.split("\n\n")
                        for p in paragraphs:
                            if rule_id in p:
                                return p
        return "Rule definition not found in spec files."
