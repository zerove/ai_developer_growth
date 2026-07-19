import os
import re
from typing import List

from .graph import DecisionGraph
from .llm_client import LLMClient
from .semantic_search import SemanticSearcher


class DecisionReasoner:
    def __init__(self, llm_client: LLMClient, adr_dir: str):
        self.llm_client = llm_client
        self.adr_dir = adr_dir
        self.graph = DecisionGraph(adr_dir)
        self.searcher = SemanticSearcher()
        if os.path.exists(adr_dir):
            self.searcher.index_directory(adr_dir)

    def _find_relevant_adrs(self, query: str) -> List[str]:
        relevant_adrs: List[str] = []
        if not os.path.exists(self.adr_dir):
            return []

        adr_id_match = re.search(r"ADR-\d+", query)
        if adr_id_match:
            adr_id = adr_id_match.group(0)
            for filename in sorted(os.listdir(self.adr_dir)):
                if not filename.endswith(".md"):
                    continue
                path = os.path.join(self.adr_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if adr_id in content:
                    relevant_adrs.insert(0, content)
            if relevant_adrs:
                return relevant_adrs

        results = self.searcher.search(query, top_k=5)
        return [content for content, _score in results]

    def explain_decision(self, query: str) -> str:
        adrs = self._find_relevant_adrs(query)
        if not adrs:
            return "No relevant ADRs found. Please provide more details or an ADR ID (e.g. ADR-001)."

        primary_adr_content = adrs[0]
        adr_id_match = re.search(r"ADR-\d+", primary_adr_content)

        causal_chain_info = ""
        if adr_id_match:
            adr_id = adr_id_match.group(0)
            chain = self.graph.trace_causality(adr_id)
            if chain:
                causal_chain_info = "Causal chain: " + " → ".join(chain)

        system_prompt = (
            "You are an expert software architect and project historian. "
            "Explain the rationale, trade-offs, and final decision based on provided ADRs. "
            "Cite ADRs specifically. Be objective and technical."
        )

        prompt = (
            f"User Query: {query}\n\n"
            f"Relevant ADRs:\n" + "\n\n".join(adrs) + "\n\n"
            f"{causal_chain_info}\n\n"
            "Provide a comprehensive explanation of why this decision was made."
        )

        return self.llm_client.generate(prompt, system_prompt=system_prompt) or "LLM failed to synthesize an explanation."
