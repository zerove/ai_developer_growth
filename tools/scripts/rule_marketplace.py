#!/usr/bin/env python3
"""Rule marketplace CLI (#9): discover, install, search, and manage rule packs.

Built-in packs:
  - security    : Common security rules (cross-language)
  - python-pack : Python anti-patterns and best practices
  - typescript-pack : TypeScript rules
  - react-pack  : React anti-patterns
  - django-pack : Django best practices
  - fastapi-pack: FastAPI best practices
  - full        : All rules for all languages

Usage:
    python tools/scripts/rule_marketplace.py list
    python tools/scripts/rule_marketplace.py search sql
    python tools/scripts/rule_marketplace.py info security
    python tools/scripts/rule_marketplace.py install security --project-dir /path/to/project
    python tools/scripts/rule_marketplace.py validate
    python tools/scripts/rule_marketplace.py export --output my-pack.yml
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _common import framework_dir as _framework_dir

# ──────────────────────────────────────────────────────────
# Built-in pack definitions
# ──────────────────────────────────────────────────────────

BUILTIN_PACKS: dict[str, dict] = {
    "security": {
        "name": "Security Rules",
        "description": "Cross-language security anti-patterns",
        "source": "common/security.yml",
        "categories": ["security"],
        "rule_count": 8,
    },
    "python-pack": {
        "name": "Python Best Practices",
        "description": "Python anti-patterns, naming conventions, and complexity rules",
        "source": "languages/python/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 21,
    },
    "typescript-pack": {
        "name": "TypeScript Best Practices",
        "description": "TypeScript anti-patterns, naming conventions, and complexity rules",
        "source": "languages/typescript/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 17,
    },
    "react-pack": {
        "name": "React Anti-patterns",
        "description": "Common React anti-patterns and best practices",
        "source": "frameworks/react/rules.d/",
        "categories": ["anti_patterns"],
        "rule_count": 8,
    },
    "vue-pack": {
        "name": "Vue Anti-patterns",
        "description": "Common Vue anti-patterns and best practices",
        "source": "frameworks/vue/rules.d/",
        "categories": ["anti_patterns"],
        "rule_count": 8,
    },
    "django-pack": {
        "name": "Django Best Practices",
        "description": "Django security, naming, and anti-patterns",
        "source": "frameworks/django/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 22,
    },
    "fastapi-pack": {
        "name": "FastAPI Best Practices",
        "description": "FastAPI anti-patterns, naming, and complexity",
        "source": "frameworks/fastapi/rules.d/",
        "categories": ["anti_patterns", "naming_conventions", "complexity"],
        "rule_count": 18,
    },
    "spring-pack": {
        "name": "Spring Boot Best Practices",
        "description": "Spring Boot anti-patterns and naming conventions",
        "source": "frameworks/spring/rules.d/",
        "categories": ["anti_patterns", "naming_conventions"],
        "rule_count": 16,
    },
    "full": {
        "name": "All Rules",
        "description": "All rules for all languages and frameworks",
        "source": "./",
        "categories": ["anti_patterns", "naming_conventions", "complexity", "security"],
        "rule_count": 350,
    },
}


# ──────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> None:
    """List all available rule packs."""
    output_json = args.json
    packs = []
    for pack_id, info in BUILTIN_PACKS.items():
        entry = {"id": pack_id, **info}
        packs.append(entry)

    if output_json:
        print(yaml.dump(packs, default_flow_style=False))
    else:
        print(f"{'Pack ID':<20} {'Rules':<8} {'Description'}")
        print("-" * 70)
        for p in packs:
            print(f"{p['id']:<20} {p['rule_count']:<8} {p['description']}")


def cmd_search(args: argparse.Namespace) -> None:
    """Search rules by keyword."""
    query = args.query.lower()
    fw = _framework_dir()
    results = []

    # Search in common rules
    common_file = fw / "common" / "security.yml"
    if common_file.exists():
        with open(common_file) as f:
            data = yaml.safe_load(f) or {}
        for rule in data.get("anti_patterns", []):
            if _matches(rule, query):
                results.append({"pack": "security", **rule})

    # Search in language rules
    langs_dir = fw / "languages"
    if langs_dir.exists():
        for lang_dir in sorted(langs_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            rules_dir = lang_dir / "rules.d"
            if not rules_dir.exists():
                continue
            for yml in rules_dir.glob("*.yml"):
                with open(yml) as f:
                    data = yaml.safe_load(f) or {}
                for category in ["anti_patterns", "naming_conventions", "complexity"]:
                    for rule in data.get(category, []):
                        if _matches(rule, query):
                            results.append(
                                {"pack": lang_dir.name, "category": category, **rule}
                            )

    # Search in framework rules
    frameworks_dir = fw / "frameworks"
    if frameworks_dir.exists():
        for fw_dir in sorted(frameworks_dir.iterdir()):
            if not fw_dir.is_dir():
                continue
            rules_dir = fw_dir / "rules.d"
            if not rules_dir.exists():
                continue
            for yml in rules_dir.glob("*.yml"):
                with open(yml) as f:
                    data = yaml.safe_load(f) or {}
                for category in ["anti_patterns", "naming_conventions", "complexity"]:
                    for rule in data.get(category, []):
                        if _matches(rule, query):
                            results.append(
                                {"pack": fw_dir.name, "category": category, **rule}
                            )

    if args.json:
        print(yaml.dump(results, default_flow_style=False))
    else:
        print(f"Found {len(results)} rules matching '{args.query}':\n")
        for r in results:
            sev = r.get("severity", "?")
            print(f"  [{sev:>7}] {r['id']}: {r.get('message', '')}")
            if r.get("pattern"):
                print(f"          pattern: {r['pattern'][:60]}")
        if not results:
            print("  No matching rules found.")


def _matches(rule: dict, query: str) -> bool:
    """Check if a rule matches a search query."""
    fields = [
        rule.get("id", ""),
        rule.get("message", ""),
        rule.get("pattern", ""),
        rule.get("fix_hint", ""),
        rule.get("category", ""),
        " ".join(rule.get("tags", [])),
    ]
    text = " ".join(fields).lower()
    return query in text


def cmd_info(args: argparse.Namespace) -> None:
    """Show details about a rule pack."""
    pack_id = args.pack
    if pack_id not in BUILTIN_PACKS:
        print(f"Unknown pack: {pack_id}")
        print(f"Available: {', '.join(BUILTIN_PACKS.keys())}")
        return

    info = BUILTIN_PACKS[pack_id]
    if args.json:
        print(yaml.dump({pack_id: info}, default_flow_style=False))
    else:
        print(f"Pack: {info['name']}")
        print(f"  ID:          {pack_id}")
        print(f"  Description: {info['description']}")
        print(f"  Rules:       ~{info['rule_count']}")
        print(f"  Categories:  {', '.join(info['categories'])}")
        print(f"  Source:      {info['source']}")

        # Show example rules from source
        src = _framework_dir() / info["source"]
        if src.is_file():
            with open(src) as f:
                data = yaml.safe_load(f) or {}
            anti = data.get("anti_patterns", [])[:3]
            if anti:
                print("\n  Example rules:")
                for rule in anti:
                    print(f"    - {rule['id']}: {rule.get('message', '')}")
        elif src.is_dir():
            print(f"\n  Source directory: {src}")
            for yml in sorted(src.glob("*.yml")):
                with open(yml) as f:
                    data = yaml.safe_load(f) or {}
                count = sum(len(data.get(c, [])) for c in info["categories"])
                print(f"    {yml.name}: {count} rules")


def cmd_install(args: argparse.Namespace) -> None:
    """Install a rule pack to .ai-rules/ in the project directory."""
    pack_id = args.pack
    if pack_id not in BUILTIN_PACKS:
        print(f"Unknown pack: {pack_id}")
        return

    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    target_dir = project_dir / ".ai-rules"
    info = BUILTIN_PACKS[pack_id]

    if args.dry_run:
        print(f"[dry-run] Would install '{pack_id}' to {target_dir}/")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    src = _framework_dir() / info["source"]

    if src.is_file():
        dest = target_dir / src.name
        shutil.copy2(src, dest)
        print(f"Installed: {dest}")
    elif src.is_dir():
        for yml in src.glob("*.yml"):
            dest = target_dir / f"{pack_id}-{yml.name}"
            shutil.copy2(yml, dest)
            print(f"Installed: {dest}")

    print(f"Pack '{pack_id}' installed to {target_dir}/")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate all installed rules in .ai-rules/."""
    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    rules_dir = project_dir / ".ai-rules"

    if not rules_dir.exists():
        print(f"No .ai-rules/ directory found in {project_dir}")
        return

    errors = 0
    for yml in sorted(rules_dir.glob("*.yml")):
        try:
            with open(yml) as f:
                data = yaml.safe_load(f)
            if not data:
                print(f"  ✗ {yml.name}: empty or invalid YAML")
                errors += 1
                continue

            rule_count = 0
            for category in ["anti_patterns", "naming_conventions", "complexity"]:
                for rule in data.get(category, []):
                    if not rule.get("id"):
                        print(f"  ✗ {yml.name}: rule missing 'id'")
                        errors += 1
                    if not rule.get("pattern") and category in ["anti_patterns", "complexity"]:
                        print(f"  ✗ {yml.name}/{rule.get('id', '?')}: missing 'pattern'")
                        errors += 1
                    if not rule.get("message"):
                        print(f"  ✗ {yml.name}/{rule.get('id', '?')}: missing 'message'")
                        errors += 1
                    rule_count += 1

            if errors == 0:
                print(f"  ✓ {yml.name}: {rule_count} rules valid")
        except yaml.YAMLError as e:
            print(f"  ✗ {yml.name}: YAML parse error: {e}")
            errors += 1

    if errors:
        print(f"\n{errors} validation errors found")
    else:
        print("\nAll rules valid ✓")


def cmd_export(args: argparse.Namespace) -> None:
    """Export current .ai-rules/ as a shareable pack."""
    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    rules_dir = project_dir / ".ai-rules"

    if not rules_dir.exists():
        print(f"No .ai-rules/ directory found in {project_dir}")
        return

    combined: dict = {"anti_patterns": [], "naming_conventions": [], "complexity": []}

    for yml in sorted(rules_dir.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f) or {}
        for category in combined:
            combined[category].extend(data.get(category, []))

    output = Path(args.output) if args.output else Path("exported-rules.yml")
    if args.dry_run:
        total = sum(len(v) for v in combined.values())
        print(f"[dry-run] Would export {total} rules to {output}")
        return

    with open(output, "w") as f:
        yaml.dump(combined, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    total = sum(len(v) for v in combined.values())
    print(f"Exported {total} rules to {output}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rule marketplace: discover, install, search, and manage rule packs"
    )
    parser.add_argument("--project-dir", type=str, help="Project directory")
    parser.add_argument("--json", action="store_true", help="JSON output")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available rule packs")

    search_p = sub.add_parser("search", help="Search rules by keyword")
    search_p.add_argument("query", type=str, help="Search query")

    info_p = sub.add_parser("info", help="Show pack details")
    info_p.add_argument("pack", type=str, help="Pack ID")

    install_p = sub.add_parser("install", help="Install a rule pack")
    install_p.add_argument("pack", type=str, help="Pack ID")
    install_p.add_argument("--dry-run", action="store_true", help="Preview only")
    install_p.add_argument("--project-dir", type=str, help="Project directory")

    validate_p = sub.add_parser("validate", help="Validate installed rules")
    validate_p.add_argument("--project-dir", type=str, help="Project directory")

    export_p = sub.add_parser("export", help="Export installed rules")
    export_p.add_argument("-o", "--output", type=str, help="Output file")
    export_p.add_argument("--dry-run", action="store_true", help="Preview only")
    export_p.add_argument("--project-dir", type=str, help="Project directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "list": cmd_list,
        "search": cmd_search,
        "info": cmd_info,
        "install": cmd_install,
        "validate": cmd_validate,
        "export": cmd_export,
    }

    commands[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
