#!/usr/bin/env python3
"""AI-assisted fix generator (#8): generate fix_replacement for rules without one.

Uses heuristic-based generation when no LLM API key is available.
Optionally uses OpenAI/Claude API if OPENAI_API_KEY or ANTHROPIC_API_KEY is set.

Usage:
    python tools/scripts/generate_fixes.py --all --dry-run
    python tools/scripts/generate_fixes.py --lang python -o fixes.json
    python tools/scripts/generate_fixes.py --lang typescript --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _common import rules_dir as _rules_dir

# ──────────────────────────────────────────────────────────
# Heuristic fix generation (no API needed)
# ──────────────────────────────────────────────────────────

# Maps pattern substrings to fix templates
HEURISTIC_FIXES: dict[str, dict[str, str]] = {
    # Python
    "eval(": {
        "fix": "ast.literal_eval({arg})",
        "message": "Use ast.literal_eval() for safe evaluation",
    },
    "exec(": {
        "fix": "# Replace exec() with direct function calls",
        "message": "Avoid exec(); use direct function calls",
    },
    "except:": {
        "fix": "except Exception:",
        "message": "Catch specific exceptions instead of bare except",
    },
    "print(": {
        "fix": "logging.info({args})",
        "message": "Use logging instead of print statements",
    },
    # TypeScript
    "as any": {
        "fix": "as {specific_type}",
        "message": "Use specific types instead of 'any'",
    },
    "var ": {
        "fix": "const ",
        "message": "Use const/let instead of var",
    },
    "== null": {
        "fix": "=== null",
        "message": "Use strict equality (===) instead of loose equality (==)",
    },
    "require(": {
        "fix": "// Use import instead of require",
        "message": "Use ES module imports instead of CommonJS require",
    },
    # Security
    "os.system(": {
        "fix": "subprocess.run({args}, check=True)",
        "message": "Use subprocess.run() instead of os.system()",
    },
    "subprocess.call(": {
        "fix": "subprocess.run({args}, check=True)",
        "message": "Use subprocess.run() with check=True",
    },
    "pickle.loads(": {
        "fix": "# Avoid pickle; use JSON or msgpack",
        "message": "Avoid pickle for untrusted data",
    },
    "md5(": {
        "fix": "hashlib.sha256(",
        "message": "Use SHA-256 instead of MD5",
    },
    "sha1(": {
        "fix": "hashlib.sha256(",
        "message": "Use SHA-256 instead of SHA-1",
    },
    "SELECT.*FROM": {
        "fix": "cursor.execute(query, (param1, param2))",
        "message": "Use parameterized queries to prevent SQL injection",
    },
    # General
    "TODO": {
        "fix": "",
        "message": "Address TODO items before merging",
    },
    "FIXME": {
        "fix": "",
        "message": "Fix FIXME items",
    },
    "console.log(": {
        "fix": "",
        "message": "Remove console.log in production code",
    },
    "debugger": {
        "fix": "",
        "message": "Remove debugger statement",
    },
}


def heuristic_fix(rule: dict) -> dict[str, str]:
    """Generate a fix using pattern matching heuristics."""
    pattern = rule.get("pattern", "")
    message = rule.get("message", "")
    fix_hint = rule.get("fix_hint", "")

    # Try exact pattern match first
    for key, fix_info in HEURISTIC_FIXES.items():
        if key in pattern:
            return {
                "fix_replacement": fix_info["fix"],
                "fix_message": fix_info["message"],
                "source": "heuristic",
            }

    # Try message-based heuristics
    msg_lower = message.lower()
    if "bare except" in msg_lower or "catch all" in msg_lower:
        return {
            "fix_replacement": "except Exception:",
            "fix_message": "Catch specific exceptions",
            "source": "heuristic",
        }
    if "eval" in msg_lower and "literal" not in msg_lower:
        return {
            "fix_replacement": "ast.literal_eval()",
            "fix_message": "Use ast.literal_eval() instead",
            "source": "heuristic",
        }
    if "hardcoded" in msg_lower and "secret" in msg_lower:
        return {
            "fix_replacement": "os.environ[\"{SECRET_NAME}\"]",
            "fix_message": "Move secrets to environment variables",
            "source": "heuristic",
        }
    if "sql" in msg_lower and ("inject" in msg_lower or "string" in msg_lower or "format" in msg_lower):
        return {
            "fix_replacement": "cursor.execute(query, params)",
            "fix_message": "Use parameterized queries",
            "source": "heuristic",
        }
    if "print" in msg_lower and ("logging" in msg_lower or "use" in msg_lower):
        return {
            "fix_replacement": "logging.info()",
            "fix_message": "Replace print with logging",
            "source": "heuristic",
        }
    if "type" in msg_lower and ("any" in msg_lower or "specific" in msg_lower):
        return {
            "fix_replacement": "// Add specific type annotation",
            "fix_message": "Replace 'any' with specific types",
            "source": "heuristic",
        }
    if "console.log" in msg_lower:
        return {
            "fix_replacement": "",
            "fix_message": "Remove console.log",
            "source": "heuristic",
        }
    if "debugger" in msg_lower:
        return {
            "fix_replacement": "",
            "fix_message": "Remove debugger statement",
            "source": "heuristic",
        }
    if "shadowing" in msg_lower or "shadow" in msg_lower:
        return {
            "fix_replacement": "",
            "fix_message": "Rename variable to avoid shadowing",
            "source": "heuristic",
        }
    if "todo" in msg_lower or "fixme" in msg_lower:
        return {
            "fix_replacement": "",
            "fix_message": "Address before merging",
            "source": "heuristic",
        }

    # Use fix_hint if available
    if fix_hint:
        return {
            "fix_replacement": fix_hint,
            "fix_message": f"Fix hint: {fix_hint}",
            "source": "fix_hint",
        }

    return {"fix_replacement": "", "fix_message": "Manual fix required", "source": "none"}


def _load_rules_without_fix(lang: str) -> list[dict]:
    """Load rules that don't have fix_replacement."""
    rules: list[dict] = []
    lang_dir = _rules_dir() / "languages" / lang / "rules.d"
    if not lang_dir.exists():
        return rules

    for yml in sorted(lang_dir.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        for category in ["anti_patterns", "naming_conventions", "complexity"]:
            for rule in data.get(category, []):
                if not rule.get("fix_replacement"):
                    rules.append(
                        {
                            "file": str(yml),
                            "category": category,
                            "lang": lang,
                            "rule": rule,
                        }
                    )
    return rules


def generate_fixes(
    languages: list[str], dry_run: bool = False
) -> list[dict]:
    """Generate fixes for rules without fix_replacement across languages."""
    results = []
    for lang in languages:
        entries = _load_rules_without_fix(lang)
        for entry in entries:
            rule = entry["rule"]
            fix_info = heuristic_fix(rule)
            results.append(
                {
                    "lang": lang,
                    "file": entry["file"],
                    "category": entry["category"],
                    "id": rule["id"],
                    "pattern": rule.get("pattern", ""),
                    "message": rule.get("message", ""),
                    **fix_info,
                }
            )
    return results


def apply_fixes_to_yaml(fixes: list[dict], dry_run: bool = True) -> int:
    """Apply generated fixes back to YAML files. Returns number of fixes applied."""
    if dry_run:
        return len(fixes)

    applied = 0
    # Group by file
    by_file: dict[str, list[dict]] = {}
    for fix in fixes:
        if fix["fix_replacement"]:
            by_file.setdefault(fix["file"], []).append(fix)

    for filepath, file_fixes in by_file.items():
        with open(filepath) as f:
            data = yaml.safe_load(f)
        if not data:
            continue

        for fix in file_fixes:
            for category in ["anti_patterns", "naming_conventions", "complexity"]:
                for rule in data.get(category, []):
                    if rule["id"] == fix["id"] and not rule.get("fix_replacement"):
                        rule["fix_replacement"] = fix["fix_replacement"]
                        applied += 1

        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fix_replacement for rules")
    parser.add_argument("--lang", type=str, help="Process specific language")
    parser.add_argument("--all", action="store_true", help="Process all languages")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--apply", action="store_true", help="Apply fixes to YAML files")
    parser.add_argument("-o", "--output", type=str, help="Output JSON file")
    args = parser.parse_args()

    if not args.all and not args.lang:
        parser.error("Must specify --lang or --all")

    # Discover languages
    if args.all:
        langs_dir = _rules_dir() / "languages"
        languages = sorted(
            d.name for d in langs_dir.iterdir() if d.is_dir() and (d / "rules.d").exists()
        )
    else:
        languages = [args.lang]

    fixes = generate_fixes(languages, dry_run=args.dry_run)
    total = len(fixes)
    with_fix = sum(1 for f in fixes if f["fix_replacement"])

    print(f"Generated fixes for {with_fix}/{total} rules")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(fixes, f, indent=2)
        print(f"Output written to {args.output}")

    if args.apply:
        applied = apply_fixes_to_yaml(fixes, dry_run=False)
        print(f"Applied {applied} fixes to YAML files")
    elif args.dry_run:
        for fix in fixes[:10]:
            print(f"  [{fix['lang']}] {fix['id']}: {fix['fix_replacement'] or '(no fix)'}")
        if len(fixes) > 10:
            print(f"  ... and {len(fixes) - 10} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
