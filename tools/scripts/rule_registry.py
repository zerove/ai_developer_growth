#!/usr/bin/env python3
"""Rule Registry (#3): central registry for rule packs with publish/subscribe.

Manages a local registry of rule packs that can be shared across projects.

Usage:
    python tools/scripts/rule_registry.py init
    python tools/scripts/rule_registry.py list
    python tools/scripts/rule_registry.py publish my-rules.yml --name my-pack
    python tools/scripts/rule_registry.py install my-pack
    python tools/scripts/rule_registry.py search security
    python tools/scripts/rule_registry.py info my-pack
    python tools/scripts/rule_registry.py remove my-pack
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import handle_error


def _registry_dir() -> Path:
    """Get the registry directory (~/.ai-rules-registry/)."""
    return Path.home() / ".ai-rules-registry"


def _registry_file() -> Path:
    return _registry_dir() / "registry.json"


def _packs_dir() -> Path:
    return _registry_dir() / "packs"


def init_registry() -> None:
    """Initialize the registry."""
    reg_dir = _registry_dir()
    reg_dir.mkdir(parents=True, exist_ok=True)
    _packs_dir().mkdir(exist_ok=True)

    if not _registry_file().exists():
        _save_registry({"packs": {}, "version": "1.0"})
        print(f"Registry initialized at {reg_dir}")
    else:
        print(f"Registry already exists at {reg_dir}")


def _load_registry() -> dict[str, Any]:
    if _registry_file().exists():
        with open(_registry_file()) as f:
            result: dict[str, Any] = json.load(f)
            return result
    return {"packs": {}, "version": "1.0"}


def _save_registry(data: dict[str, Any]) -> None:
    with open(_registry_file(), "w") as f:
        json.dump(data, f, indent=2)


def _file_hash(filepath: Path) -> str:
    try:
        h = hashlib.sha256()
        h.update(filepath.read_bytes())
        return h.hexdigest()[:16]
    except (OSError, ValueError):
        return ""


def cmd_init(args: argparse.Namespace) -> None:
    init_registry()


def cmd_list(args: argparse.Namespace) -> None:
    reg = _load_registry()
    packs = reg.get("packs", {})

    if args.json:
        print(json.dumps(packs, indent=2))
        return

    if not packs:
        print("No packs in registry. Use 'publish' to add one.")
        return

    print(f"{'Name':<25} {'Version':<10} {'Rules':<8} {'Updated'}")
    print("-" * 65)
    for name, info in packs.items():
        print(
            f"{name:<25} {info.get('version', '?'):<10} {info.get('rule_count', '?'):<8} {info.get('updated', '?')[:10]}"
        )


def cmd_publish(args: argparse.Namespace) -> None:
    """Publish a YAML rule file to the registry."""
    source = Path(args.source)
    if not source.exists():
        print(f"File not found: {source}")
        return

    name = args.name or source.stem
    version = args.version or "1.0.0"

    # Load and validate YAML
    with open(source) as f:
        data = yaml.safe_load(f)
    if not data:
        print(f"Invalid YAML: {source}")
        return

    # Count rules
    rule_count = 0
    for category in ["anti_patterns", "naming_conventions", "complexity"]:
        rule_count += len(data.get(category, []))

    # Copy to registry
    packs_dir = _packs_dir()
    packs_dir.mkdir(exist_ok=True)
    dest = packs_dir / f"{name}.yml"
    shutil.copy2(source, dest)

    # Update registry
    reg = _load_registry()
    reg["packs"][name] = {
        "version": version,
        "source": str(source),
        "rule_count": rule_count,
        "hash": _file_hash(dest),
        "published": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "description": args.description or f"Rule pack: {name}",
        "tags": args.tags.split(",") if args.tags else [],
    }
    _save_registry(reg)

    print(f"Published '{name}' v{version} ({rule_count} rules)")


def cmd_install(args: argparse.Namespace) -> None:
    """Install a pack from registry to project .ai-rules/."""
    reg = _load_registry()
    packs = reg.get("packs", {})

    if args.pack not in packs:
        print(f"Pack '{args.pack}' not found in registry")
        print(f"Available: {', '.join(packs.keys())}")
        return

    pack_info = packs[args.pack]
    pack_file = _packs_dir() / f"{args.pack}.yml"

    if not pack_file.exists():
        print(f"Pack file not found: {pack_file}")
        return

    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    target_dir = project_dir / ".ai-rules"
    target_dir.mkdir(parents=True, exist_ok=True)

    dest = target_dir / f"{args.pack}.yml"
    shutil.copy2(pack_file, dest)
    print(f"Installed '{args.pack}' v{pack_info['version']} to {dest}")


def cmd_search(args: argparse.Namespace) -> None:
    """Search packs by keyword."""
    reg = _load_registry()
    query = args.query.lower()
    results = {}

    for name, info in reg.get("packs", {}).items():
        text = f"{name} {info.get('description', '')} {' '.join(info.get('tags', []))}".lower()
        if query in text:
            results[name] = info

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print(f"No packs matching '{args.query}'")
            return
        print(f"Found {len(results)} packs:")
        for name, info in results.items():
            print(f"  {name} v{info['version']}: {info.get('description', '')}")


def cmd_info(args: argparse.Namespace) -> None:
    """Show pack details."""
    reg = _load_registry()
    packs = reg.get("packs", {})

    if args.pack not in packs:
        print(f"Pack '{args.pack}' not found")
        return

    info = packs[args.pack]
    if args.json:
        print(json.dumps({args.pack: info}, indent=2))
    else:
        print(f"Pack: {args.pack}")
        for k, v in info.items():
            print(f"  {k}: {v}")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a pack from registry."""
    reg = _load_registry()
    packs = reg.get("packs", {})

    if args.pack not in packs:
        print(f"Pack '{args.pack}' not found")
        return

    # Remove file
    pack_file = _packs_dir() / f"{args.pack}.yml"
    pack_file.unlink(missing_ok=True)

    # Remove from registry
    del packs[args.pack]
    _save_registry(reg)
    print(f"Removed '{args.pack}' from registry")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(description="Rule Registry: manage rule packs")
    parser.add_argument("--json", action="store_true", help="JSON output")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize registry")
    sub.add_parser("list", help="List registered packs")

    pub = sub.add_parser("publish", help="Publish a rule pack")
    pub.add_argument("source", type=str, help="YAML file to publish")
    pub.add_argument("--name", type=str, help="Pack name")
    pub.add_argument("--version", type=str, help="Version string")
    pub.add_argument("--description", type=str, help="Pack description")
    pub.add_argument("--tags", type=str, help="Comma-separated tags")

    inst = sub.add_parser("install", help="Install a pack")
    inst.add_argument("pack", type=str, help="Pack name")
    inst.add_argument("--project-dir", type=str, help="Project directory")

    sch = sub.add_parser("search", help="Search packs")
    sch.add_argument("query", type=str, help="Search query")

    inf = sub.add_parser("info", help="Show pack details")
    inf.add_argument("pack", type=str, help="Pack name")

    rm = sub.add_parser("remove", help="Remove a pack")
    rm.add_argument("pack", type=str, help="Pack name")

    return parser


def _dispatch_command(args: argparse.Namespace) -> int:
    """Dispatch the parsed command to the appropriate handler."""
    if not args.command:
        return 0

    commands: dict[str, Callable[[argparse.Namespace], None]] = {
        "init": cmd_init,
        "list": cmd_list,
        "publish": cmd_publish,
        "install": cmd_install,
        "search": cmd_search,
        "info": cmd_info,
        "remove": cmd_remove,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        return _dispatch_command(args)
    except Exception as e:
        handle_error(e, script="rule_registry")
        return 1


if __name__ == "__main__":
    sys.exit(main())
