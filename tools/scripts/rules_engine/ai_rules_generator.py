"""AI-driven rule generation: analyzes a codebase and generates custom rules.

Usage:
    python -m tools.scripts.rules_engine.ai_rules_generator <project_path> [--output rules.yml]

Analyzes the codebase for patterns, anti-patterns, and generates
a custom .adg/rules.yml configuration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

# Patterns that indicate potential rule candidates
PATTERN_DETECTORS: list[dict[str, Any]] = [
    {
        "id": "detected-eval-usage",
        "pattern": r"\beval\s*\(|\bexec\s*\(",
        "name": "Dynamic code execution",
        "severity": "error",
        "category": "security",
        "message": "eval/exec detected in codebase - security risk",
        "fix_hint": "Replace with safer alternatives",
    },
    {
        "id": "detected-print-logging",
        "pattern": r"\bprint\s*\(|\bprintln\s*\(",
        "name": "Print statements",
        "severity": "warning",
        "category": "code_quality",
        "message": "Print statements should use proper logging",
        "fix_hint": "Replace with logging module",
    },
    {
        "id": "detected-todo-fixme",
        "pattern": r"TODO|FIXME|HACK|XXX",
        "name": "Unresolved TODO/FIXME",
        "severity": "info",
        "category": "code_quality",
        "message": "Unresolved TODO/FIXME comments found",
        "fix_hint": "Address or create tickets for these items",
    },
    {
        "id": "detected-hardcoded-string",
        "pattern": r'(?:(?:url|endpoint|host|address)\s*=\s*["\']https?://)',
        "name": "Hardcoded URL",
        "severity": "warning",
        "category": "config",
        "message": "Hardcoded URLs should use configuration",
        "fix_hint": "Move to environment variables or config files",
    },
    {
        "id": "detected-empty-catch",
        "pattern": r"catch\s*(?:\([^)]*\))?\s*\{\s*\}|except.*:\s*pass\s*$",
        "name": "Empty catch/except block",
        "severity": "error",
        "category": "error_handling",
        "message": "Empty exception handlers hide bugs",
        "fix_hint": "Log the exception or re-raise",
    },
    {
        "id": "detected-bare-except",
        "pattern": r"except\s*:",
        "name": "Bare except clause",
        "severity": "error",
        "category": "error_handling",
        "message": "Bare except catches all exceptions including SystemExit",
        "fix_hint": "Catch specific exceptions",
    },
    {
        "id": "detected-magic-numbers",
        "pattern": r"(?:if|while|for)\s*\(?\s*\w+\s*[><=!]+\s*(?:0x[0-9a-fA-F]+|\d{3,})\b",
        "name": "Magic numbers",
        "severity": "info",
        "category": "code_quality",
        "message": "Magic numbers should be named constants",
        "fix_hint": "Extract to named constants",
    },
    {
        "id": "detected-deep-nesting",
        "pattern": r"    (?:if|for|while|try).*\n(?:        (?:if|for|while|try).*\n){2,}",
        "name": "Deep nesting",
        "severity": "warning",
        "category": "code_quality",
        "message": "Deeply nested code reduces readability",
        "fix_hint": "Extract into helper functions or use early returns",
    },
    {
        "id": "detected-console-log",
        "pattern": r"console\.(?:log|debug|warn|error)\s*\(",
        "name": "Console.log usage",
        "severity": "info",
        "category": "code_quality",
        "message": "Console.log should not be in production code",
        "fix_hint": "Use a proper logging library",
    },
    {
        "id": "detected-sql-string",
        "pattern": r'(?:execute|query)\s*\(.*(?:f["\']|\.format\(|%\s)',
        "name": "SQL injection risk",
        "severity": "error",
        "category": "security",
        "message": "String formatting in SQL enables injection",
        "fix_hint": "Use parameterized queries",
    },
]


def detect_language_from_files(files: list[Path]) -> str:
    """Detect the primary language from file extensions."""
    ext_counter: Counter[str] = Counter()
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".rs": "rust",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".kt": "kotlin",
        ".swift": "swift",
    }
    for f in files:
        ext = f.suffix.lower()
        if ext in ext_map:
            ext_counter[ext_map[ext]] += 1
    if ext_counter:
        return ext_counter.most_common(1)[0][0]
    return "unknown"


def _collect_code_files(project_path: Path) -> list[Path]:
    """Collect code files from project, ignoring common directories."""
    code_extensions = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".rs",
        ".java",
        ".go",
        ".rb",
        ".cs",
        ".kt",
        ".swift",
    }
    ignore_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".cache",
    }

    files: list[Path] = []
    for ext in code_extensions:
        files.extend(f for f in project_path.rglob(f"*{ext}") if not any(d in f.parts for d in ignore_dirs))
    return files


def _analyze_files(
    files: list[Path],
) -> tuple[str, int, list[dict[str, Any]], dict[str, int]]:
    """Analyze files to detect patterns and count occurrences."""
    language = detect_language_from_files(files)
    total_lines = 0
    detected_patterns: list[dict[str, Any]] = []
    pattern_counts: dict[str, int] = {}

    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
            lines = content.splitlines()
            total_lines += len(lines)

            for detector in PATTERN_DETECTORS:
                matches = re.findall(detector["pattern"], content, re.MULTILINE)
                if matches:
                    if detector["id"] not in pattern_counts:
                        pattern_counts[detector["id"]] = 0
                        detected_patterns.append(detector)
                    pattern_counts[detector["id"]] += len(matches)
        except (UnicodeDecodeError, OSError):
            continue

    return language, total_lines, detected_patterns, pattern_counts


def _build_rules(
    language: str,
    detected_patterns: list[dict[str, Any]],
    pattern_counts: dict[str, int],
) -> dict[str, Any]:
    """Build rules dictionary from detected patterns."""
    rules: dict[str, Any] = {
        "language": language,
        "config_version": "1.0",
        "source": "auto-generated",
        "generated_at": datetime.now().isoformat(),
        "anti_patterns": [],
    }

    for pattern in detected_patterns:
        count = pattern_counts.get(pattern["id"], 0)
        rules["anti_patterns"].append(
            {
                "id": pattern["id"],
                "name": pattern["name"],
                "severity": pattern["severity"],
                "category": pattern["category"],
                "pattern": PATTERN_DETECTORS[PATTERN_DETECTORS.index(pattern)]["pattern"],
                "message": f"{pattern['message']} (found {count} occurrences)",
                "fix_hint": pattern["fix_hint"],
            }
        )

    return rules


def analyze_project(project_path: Path) -> dict[str, Any]:
    """Analyze a project and generate rule suggestions.

    Args:
        project_path: Root of the project to analyze.

    Returns:
        Dict with detected patterns, stats, and generated rules.
    """
    files = _collect_code_files(project_path)

    if not files:
        return {"error": "No code files found", "files": 0}

    language, total_lines, detected_patterns, pattern_counts = _analyze_files(files)
    rules = _build_rules(language, detected_patterns, pattern_counts)

    return {
        "language": language,
        "files_analyzed": len(files),
        "total_lines": total_lines,
        "detected_patterns": len(detected_patterns),
        "pattern_counts": pattern_counts,
        "rules": rules,
    }


def format_analysis(result: dict[str, Any], *, format: str = "text") -> str:
    """Format analysis results."""
    if "error" in result:
        return f"Error: {result['error']}"

    if format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)

    lines = [
        "🔍 AI Rule Generation - Project Analysis",
        "=" * 50,
        f"Language: {result['language']}",
        f"Files analyzed: {result['files_analyzed']}",
        f"Total lines: {result['total_lines']}",
        f"Patterns detected: {result['detected_patterns']}",
        "",
        "Detected patterns:",
    ]

    for pattern_id, count in sorted(result["pattern_counts"].items(), key=lambda x: -x[1]):
        lines.append(f"  {pattern_id}: {count} occurrences")

    lines.append(f"\nGenerated {len(result['rules']['anti_patterns'])} rules")

    return "\n".join(lines)


def main() -> None:
    """CLI entry point for AI rule generation."""
    parser = argparse.ArgumentParser(description="AI-driven rule generation")
    parser.add_argument("project_path", type=Path, help="Project root to analyze")
    parser.add_argument("--output", "-o", type=Path, help="Output YAML file")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    if not args.project_path.exists():
        print(f"Error: {args.project_path} not found", file=sys.stderr)
        sys.exit(1)

    result = analyze_project(args.project_path)
    print(format_analysis(result, format=args.format))

    if args.output:
        try:
            import yaml

            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                yaml.dump(result["rules"], f, default_flow_style=False, allow_unicode=True)
            print(f"\n✅ Rules written to {args.output}")
        except ImportError:
            # Fallback to JSON
            args.output.write_text(json.dumps(result["rules"], indent=2, ensure_ascii=False))
            print(f"\n✅ Rules written to {args.output} (JSON - install PyYAML for YAML output)")
    elif not sys.stdin.isatty():
        # Pipe mode: output rules to stdout
        try:
            import yaml

            print("\n---\n# Generated rules YAML")
            print(yaml.dump(result["rules"], default_flow_style=False, allow_unicode=True))
        except ImportError:
            print("\n---\n# Generated rules JSON")
            print(json.dumps(result["rules"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
