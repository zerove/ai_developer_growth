from __future__ import annotations

import argparse
import json
import logging

from ._shared import (
    Any,
    Path,
)


def _apply_recommendations(project_dir: Path, result: dict[str, Any]) -> int:
    """Write recommended rules to .adg/rules.yml."""
    rules_dir = project_dir / ".adg"
    rules_dir.mkdir(exist_ok=True)
    rules_file = rules_dir / "rules.yml"

    # Load existing rules if any
    existing_rules = _load_existing_rules(rules_file)
    existing_ids = {r.get("id") for r in existing_rules.get("anti_patterns", [])}

    # Add new recommendations as custom rules
    new_rules = _build_new_rules(result, existing_ids)

    if new_rules:
        existing_rules.setdefault("anti_patterns", []).extend(new_rules)
        _save_rules(rules_file, existing_rules)

        print(f"\n✅ Applied {len(new_rules)} new rules to {rules_file}")
        for r in new_rules:
            print(f"   + {r['id']} ({r['severity']})")
    else:
        print(f"\nℹ️  No new rules to apply (all already exist in {rules_file})")

    return 0


def _build_new_rules(result: dict[str, Any], existing_ids: set[str]) -> list[dict[str, Any]]:
    """Build new rules from recommendations."""
    new_rules: list[dict[str, Any]] = []
    for rec in result["recommendations"]:
        if rec["rule_id"] not in existing_ids:
            new_rules.append(
                {
                    "id": rec["rule_id"],
                    "name": rec["name"],
                    "severity": rec["severity"],
                    "category": rec["category"],
                    "message": rec["reason"],
                    "fix_hint": f"Auto-generated from pattern: {rec['example']['code']}",
                }
            )
            existing_ids.add(rec["rule_id"])
    return new_rules


def _load_existing_rules(rules_file: Path) -> dict[str, Any]:
    """Load existing rules from file."""
    existing_rules: dict[str, Any] = {"anti_patterns": []}
    if rules_file.exists():
        try:
            import yaml

            with open(rules_file) as f:
                data = yaml.safe_load(f)
                if data and "anti_patterns" in data:
                    existing_rules = data
        except Exception as exc:
            logging.getLogger(__name__).debug(f"Skipped unreadable rules file {rules_file}: {exc}")
    return existing_rules


def _save_rules(rules_file: Path, existing_rules: dict[str, Any]) -> None:
    """Save rules to file."""
    import yaml

    existing_rules["config_version"] = "1.0"
    existing_rules["source"] = "auto-generated-by-recommend"

    with open(rules_file, "w") as f:
        yaml.dump(existing_rules, f, sort_keys=False, allow_unicode=True)


def cmd_recommend(args: argparse.Namespace) -> int:
    """AI-powered rule recommendations."""
    from tools.ai_recommender import format_recommendations_text, recommend_rules

    target = Path(args.path).resolve()
    result = recommend_rules(target, args.max)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_recommendations_text(result))

    # Apply: auto-generate .adg/rules.yml
    if getattr(args, "apply", False):
        return _apply_recommendations(target, result)

    return 0
