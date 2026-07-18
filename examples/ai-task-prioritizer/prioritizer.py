class Prioritizer:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def prioritize(self, tasks):
        # 1. Get scores from LLM
        scores = self.llm_client.get_scores(tasks)
        
        # 2. Calculate priority score and assign category
        prioritized = []
        for item in scores:
            value = int(item.get("value", 0))
            effort = int(item.get("effort", 1)) # Avoid division by zero
            score = value / effort
            
            category = self._get_category(value, effort)
            
            prioritized.append({
                "task": item["task"],
                "value": value,
                "effort": effort,
                "score": score,
                "category": category
            })
        
        # 3. Sort by score descending
        prioritized.sort(key=lambda x: x["score"], reverse=True)
        return prioritized

    def _get_category(self, value, effort):
        if value >= 7 and effort <= 3:
            return "Quick Win (立即执行)"
        elif value >= 7:
            return "Major Project (计划执行)"
        elif effort <= 3:
            return "Fill-ins (碎片时间)"
        else:
            return "Thankless Task (考虑放弃)"
