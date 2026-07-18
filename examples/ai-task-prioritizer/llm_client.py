import os
import json
from typing import List, Dict

class LLMClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("LLM_API_KEY")

    def get_scores(self, tasks: List[str]) -> List[Dict]:
        if not self.api_key:
            raise ValueError("LLM_API_KEY environment variable is not set.")
        
        # Simulation: return strings instead of ints to trigger a bug
        import random
        random.seed(42)
        return [{"task": t, "value": str(random.randint(1, 10)), "effort": str(random.randint(1, 10))} for t in tasks]

    def _build_prompt(self, tasks: List[str]) -> str:
        task_list_str = "\n".join([f"- {t}" for t in tasks])
        return (
            f"Evaluate the following tasks based on Value (1-10) and Effort (1-10).\n"
            f"Return a JSON object with a 'tasks' key containing a list of objects: "
            f"[{{'task': '...', 'value': int, 'effort': int}}]"
        )
