#!/usr/bin/env python3
"""Rule marketplace CLI (#9): discover, install, search, and manage rule packs.

Delegates core logic to rule_catalog.py. This file is the CLI entry point.

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
import sys
from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import framework_dir as _framework_dir
from tools.scripts._common import handle_error
from tools.scripts.rule_catalog import (
    BUILTIN_PACKS,
    export_rules,
    get_pack_info,
    install_pack,
    search_rules,
    validate_rules,
)

# ──────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> None:
    """List all available rule packs."""
    packs = [{"id": pid, **info} for pid, info in BUILTIN_PACKS.items()]

    if args.json:
        print(yaml.dump(packs, default_flow_style=False))
    else:
        print(f"{'Pack ID':<20} {'Rules':<8} {'Description'}")
        print("-" * 70)
        for p in packs:
            print(f"{p['id']:<20} {p['rule_count']:<8} {p['description']}")


def cmd_search(args: argparse.Namespace) -> None:
    """Search rules by keyword."""
    results = search_rules(args.query.lower())

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


def cmd_info(args: argparse.Namespace) -> None:
    """Show details about a rule pack (V2.21 P5-32 拆分: 抽 _print_pack_info_text + _show_pack_examples)."""
    info = get_pack_info(args.pack)
    if not info:
        print(f"Unknown pack: {args.pack}")
        print(f"Available: {', '.join(BUILTIN_PACKS.keys())}")
        return

    if args.json:
        print(yaml.dump({args.pack: info}, default_flow_style=False))
        return

    _print_pack_info_text(args.pack, info)
    _show_pack_examples(info)


def _print_pack_info_text(pack_id: str, info: dict[str, Any]) -> None:
    """打印 pack 详细信息 (模块级 helper).

    Args:
        pack_id: 包 ID
        info: get_pack_info 返回的字典
    """
    print(f"Pack: {info['name']}")
    print(f"  ID:          {pack_id}")
    print(f"  Description: {info['description']}")
    print(f"  Rules:       ~{info['rule_count']}")
    print(f"  Categories:  {', '.join(info['categories'])}")
    print(f"  Source:      {info['source']}")


def _print_file_examples(src: Path) -> None:
    """打印单文件 pack 的示例规则 (Phase 36c cc 拆分: 从 _show_pack_examples 抽出)."""
    with open(src) as f:
        data = yaml.safe_load(f) or {}
    anti = data.get("anti_patterns", [])[:3]
    if anti:
        print("\n  Example rules:")
        for rule in anti:
            print(f"    - {rule['id']}: {rule.get('message', '')}")


def _print_dir_examples(src: Path, info: dict[str, Any]) -> None:
    """打印目录 pack 的规则统计 (Phase 36c cc 拆分: 从 _show_pack_examples 抽出)."""
    print(f"\n  Source directory: {src}")
    for yml in sorted(src.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f) or {}
        count = sum(len(data.get(c, [])) for c in info["categories"])
        print(f"    {yml.name}: {count} rules")


def _show_pack_examples(info: dict[str, Any]) -> None:
    """显示 pack 示例规则 (单文件 or 目录, 模块级 helper).

    Args:
        info: get_pack_info 返回的字典
    """
    src = _framework_dir() / info["source"]
    if src.is_file():
        _print_file_examples(src)
    elif src.is_dir():
        _print_dir_examples(src, info)


def cmd_install(args: argparse.Namespace) -> None:
    """Install a rule pack to .ai-rules/ in the project directory."""
    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()

    if args.dry_run:
        print(f"[dry-run] Would install '{args.pack}' to {project_dir / '.ai-rules'}/")
        return

    try:
        installed = install_pack(args.pack, project_dir)
        for p in installed:
            print(f"Installed: {p}")
        if installed:
            print(f"Pack '{args.pack}' installed to {project_dir / '.ai-rules'}/")
        else:
            print(f"Pack '{args.pack}' has no files to install")
    except ValueError as e:
        print(str(e))


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate all installed rules in .ai-rules/."""
    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    rules_dir = project_dir / ".ai-rules"

    total, errors, messages = validate_rules(rules_dir)

    if not rules_dir.exists():
        print(f"No .ai-rules/ directory found in {project_dir}")
        return

    for msg in messages:
        print(f"  ✗ {msg}")
    if errors == 0 and total > 0:
        print(f"  ✓ {total} rules valid")
    elif errors:
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

    output = Path(args.output) if args.output else Path("exported-rules.yml")

    if args.dry_run:
        total, _ = export_rules(rules_dir, output)
        print(f"[dry-run] Would export {total} rules to {output}")
        return

    total, combined = export_rules(rules_dir, output)
    with open(output, "w") as f:
        yaml.dump(combined, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"Exported {total} rules to {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule marketplace: discover, install, search, and manage rule packs")
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

    try:
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
    except Exception as e:
        handle_error(e, script="rule_marketplace")
        return 1


if __name__ == "__main__":
    sys.exit(main())
