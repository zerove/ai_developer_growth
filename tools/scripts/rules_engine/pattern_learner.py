"""Pattern learner — learns new anti-pattern rules from codebase analysis.

Analyzes check results from the rules engine to identify recurring issues
that could be converted into new anti-pattern rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.checker import check_directory
from tools.scripts.rules_engine.models import Issue


class PatternLearner:
    """Learns common issue patterns from a codebase to suggest new rules."""

    MIN_OCCURRENCES = 3  # Minimum occurrences to suggest a new rule
    SIMILARITY_THRESHOLD = 0.6  # Message similarity for grouping

    def learn_from_directory(self, project_path: Path) -> list[dict[str, Any]]:
        """Analyze codebase and identify frequent violation patterns.

        Args:
            project_path: Root directory to analyze.

        Returns:
            List of candidate rules with pattern, message, and frequency.
        """
        # Run the rules engine to collect all issues
        results = check_directory(project_path)

        # Aggregate issues by message similarity
        pattern_groups: dict[str, list[Issue]] = {}

        for result in results:
            for issue in result.issues:
                # Use truncated message as key for grouping
                key = issue.message[:60]
                if key not in pattern_groups:
                    pattern_groups[key] = []
                pattern_groups[key].append(issue)

        # Filter to frequent patterns and convert to rule suggestions
        rules: list[dict[str, Any]] = []
        for msg_key, issues in pattern_groups.items():
            if len(issues) >= self.MIN_OCCURRENCES:
                example = issues[0]
                rules.append(
                    {
                        "pattern": f"Suggested: {example.rule_id}",
                        "message": example.message,
                        "severity": example.severity,
                        "category": example.category,
                        "frequency": len(issues),
                        "files": list({i.file for i in issues}),
                        "confidence": min(len(issues) / 10, 1.0),
                    }
                )

        if not rules:
            rules.append(
                {
                    "pattern": "no-frequent-issues",
                    "message": "未发现高频违规模式",
                    "frequency": 0,
                    "confidence": 0,
                }
            )

        return rules


def run_pattern_learning(project_path: Path) -> None:
    """CLI entry point: analyze and print candidate rules."""
    learner = PatternLearner()
    patterns = learner.learn_from_directory(project_path)
    print(f"🔍 AI 学习完成，发现 {len(patterns)} 个潜在治理规则")
    for p in patterns:
        freq = p.get("frequency", 0)
        conf = p.get("confidence", 0)
        if freq > 0:
            print(f"  [{p.get('severity', 'info')}] {p['message']}")
            print(f"    频率: {freq}次 | 置信度: {conf:.0%}")
