"""
ADG AI Rule Recommender - Suggest governance rules based on code patterns.

Uses static analysis heuristics to recommend rules for a codebase.
No LLM required - works offline with pattern matching.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from tools.scripts.adg_cli import (
    detect_language,
    load_rules_for_language,
    _detect_language_from_file,
)


# ─────────────────────────────────────────────────────────────
# Pattern-based rule recommendations (loaded from YAML)
# ─────────────────────────────────────────────────────────────

_PATTERNS_FILE = Path(__file__).parent / "patterns.yml"


def _load_patterns() -> dict[str, list[dict[str, Any]]]:
    """Load code smell patterns from the external YAML file."""
    with open(_PATTERNS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


CODE_SMELL_PATTERNS: dict[str, list[dict[str, Any]]] = _load_patterns()


def analyze_code_patterns(
    file_path: Path,
    content: str | None = None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Analyze code for patterns that suggest specific rules."""
    if content is None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

    if language is None:
        ext = file_path.suffix.lower()
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".tsx": "typescript", ".jsx": "javascript", ".rs": "rust",
            ".go": "go", ".java": "java",
        }
        language = lang_map.get(ext)

    if not language or language not in CODE_SMELL_PATTERNS:
        return []

    recommendations = []
    patterns = CODE_SMELL_PATTERNS[language]

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern_def in patterns:
            if re.search(pattern_def["pattern"], line):
                recommendations.append({
                    "rule": pattern_def["recommendation"],
                    "reason": pattern_def["reason"],
                    "line": line_num,
                    "code": line.strip(),
                    "file": str(file_path),
                })

    return recommendations


def recommend_rules(
    project_dir: Path,
    max_recommendations: int = 20,
) -> dict[str, Any]:
    """Analyze a project and recommend governance rules."""
    detected = detect_language(project_dir)
    language = detected.get("language", "unknown")

    # Scan code files
    all_recommendations: list[dict[str, Any]] = []
    files_scanned = 0
    files_with_issues = 0

    for ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java"]:
        for file_path in project_dir.rglob(f"*{ext}"):
            # Skip common non-source directories
            parts = file_path.parts
            if any(skip in parts for skip in ["node_modules", ".git", "target", "__pycache__", "venv", ".venv"]):
                continue

            try:
                recs = analyze_code_patterns(file_path, language=language)
                all_recommendations.extend(recs)
                files_scanned += 1
                if recs:
                    files_with_issues += 1
            except Exception:
                continue

    # Deduplicate and rank
    seen_rules: set[str] = set()
    unique_recs: list[dict[str, Any]] = []
    for rec in all_recommendations:
        key = f"{rec['rule']}:{rec['file']}:{rec['line']}"
        if key not in seen_rules:
            seen_rules.add(key)
            unique_recs.append(rec)

    # Sort by frequency of rule
    rule_counts: dict[str, int] = {}
    for rec in unique_recs:
        rule_counts[rec["rule"]] = rule_counts.get(rec["rule"], 0) + 1

    unique_recs.sort(key=lambda r: rule_counts.get(r["rule"], 0), reverse=True)

    # Load available rules
    available_rules = load_rules_for_language(language)
    rule_lookup = {r.get("id", ""): r for r in available_rules.get("anti_patterns", [])}

    # Build recommendations
    recommendations_list = []
    for rec in unique_recs[:max_recommendations]:
        rule_info = rule_lookup.get(rec["rule"], {})
        recommendations_list.append({
            "rule_id": rec["rule"],
            "name": rule_info.get("name", rec["rule"]),
            "severity": rule_info.get("severity", "warning"),
            "category": rule_info.get("category", "code_quality"),
            "reason": rec["reason"],
            "affected_files": len([r for r in unique_recs if r["rule"] == rec["rule"]]),
            "example": {"file": rec["file"], "line": rec["line"], "code": rec["code"]},
        })

    # Deduplicate by rule_id, keep highest count
    seen_rules_final: set[str] = set()
    final_recommendations = []
    for rec in recommendations_list:
        if rec["rule_id"] not in seen_rules_final:
            seen_rules_final.add(rec["rule_id"])
            final_recommendations.append(rec)

    return {
        "language": language,
        "framework": detected.get("framework"),
        "files_scanned": files_scanned,
        "files_with_issues": files_with_issues,
        "total_recommendations": len(final_recommendations),
        "recommendations": final_recommendations,
    }


def format_recommendations_text(result: dict[str, Any]) -> str:
    """Format recommendations as human-readable text."""
    lines = [
        f"ADG Rule Recommendations for {result['language']}",
        f"Files scanned: {result['files_scanned']}",
        f"Files with issues: {result['files_with_issues']}",
        f"Recommendations: {result['total_recommendations']}",
        "",
    ]

    for i, rec in enumerate(result["recommendations"], 1):
        lines.append(f"{i}. [{rec['severity'].upper()}] {rec['rule_id']}")
        lines.append(f"   {rec['reason']}")
        lines.append(f"   Affected files: {rec['affected_files']}")
        lines.append(f"   Example: {rec['example']['file']}:{rec['example']['line']}")
        lines.append(f"   Code: {rec['example']['code']}")
        lines.append("")

    return "\n".join(lines)
