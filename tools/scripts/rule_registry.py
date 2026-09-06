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
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import file_hash, handle_error


def init_registry() -> None:
    """Initialize the registry."""
    reg_dir = _registry_dir()
    packs_dir = _packs_dir()
    if reg_dir.exists() and packs_dir.exists():
        print("✅ Registry already exists")
        return
    reg_dir.mkdir(parents=True, exist_ok=True)
    packs_dir.mkdir(parents=True, exist_ok=True)
    _save_registry({"packs": {}})
    print("✅ Registry initialized")


def _registry_dir() -> Path:
    """Get the registry directory path."""
    return Path.home() / ".jcode" / "registry"


def _packs_dir() -> Path:
    """Get the packs directory path."""
    return Path.home() / ".jcode" / "registry" / "packs"


def _registry_file() -> Path:
    """Get the registry file path."""
    return _registry_dir() / "registry.json"


# ──────────────────────────────────────────────────────────
# Core Registry Operations
# ──────────────────────────────────────────────────────────


def _load_registry() -> dict[str, Any]:
    """Load registry from disk."""
    reg_file = _registry_file()
    if reg_file.exists():
        try:
            with open(reg_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {"packs": {}, "version": "1.0"}
        except json.JSONDecodeError:
            return {"packs": {}, "version": "1.0"}
    return {"packs": {}, "version": "1.0"}


def _save_registry(data: dict[str, Any]) -> None:
    """Save registry to disk."""
    _registry_file().parent.mkdir(parents=True, exist_ok=True)
    with open(_registry_file(), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_disk_cache() -> dict[str, Any]:
    """Load rules from disk cache."""
    cache_file = _registry_file().parent / "rules_cache.json"
    if cache_file.exists():
        try:
            import json

            with open(cache_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_disk_cache(data: dict[str, Any]) -> None:
    """Save rules to disk cache."""
    import json

    cache_file = _registry_file().parent / "rules_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ──────────────────────────────────────────────────────────
# CLI Commands
# ──────────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize the registry."""
    init_registry()


def cmd_list(args: argparse.Namespace) -> None:
    """List all available rule packs."""
    reg = _load_registry()
    packs = reg.get("packs", {})
    if not packs:
        if getattr(args, "json", False):
            print(json.dumps({}, ensure_ascii=False))
        else:
            print("No packs")
        return
    if getattr(args, "json", False):
        print(json.dumps(packs, ensure_ascii=False))
        return
    for pack_id, info in packs.items():
        print(f"  {pack_id}: v{info.get('version', '?')} - {info.get('description', 'No description')}")


def cmd_publish(args: argparse.Namespace) -> None:
    """Publish a rule pack to the registry."""
    source = Path(args.source)
    if not source.exists():
        print(f"not found: {source}")
        return

    name = args.name or source.stem
    version = args.version or "1.0.0"

    # Load source pack
    with open(source) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        print("Invalid pack format")
        return

    rule_count = len(data.get("anti_patterns", []))
    if rule_count == 0:
        print("Empty pack")
        return

    # Copy to registry
    dest_dir = _registry_file().parent / "packs" / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{version}.yml"
    shutil.copy2(args.source, dest)

    # Update registry
    reg = _load_registry()
    reg["packs"][name] = {
        "version": version,
        "source": str(source),
        "rule_count": rule_count,
        "hash": file_hash(dest),
        "published": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "description": args.description or f"Rule pack: {name}",
        "tags": args.tags.split(",") if args.tags else [],
    }
    _save_registry(reg)

    print(f"✅ Published: {name} v{version} ({rule_count} rules)")


def cmd_install(args: argparse.Namespace) -> None:
    """Install a rule pack to a project."""
    reg = _load_registry()
    pack_name = getattr(args, "pack", getattr(args, "name", None))
    pack = reg.get("packs", {}).get(pack_name)
    if not pack:
        print(f"not found: {pack_name}")
        return

    project_dir = getattr(args, "project_dir", getattr(args, "dest", None))
    dest = Path(project_dir) if project_dir else Path(".")
    dest.mkdir(parents=True, exist_ok=True)

    # Create .ai-rules directory
    ai_rules_dir = dest / ".ai-rules"
    ai_rules_dir.mkdir(parents=True, exist_ok=True)

    # Copy rules - if pack has explicit "rules" list, use it; otherwise use the pack's source file
    rules = pack.get("rules")
    if rules:
        for rule_file in rules:
            src = Path(pack["source"]).parent / rule_file
            dst = ai_rules_dir / rule_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    elif "source" in pack and Path(pack["source"]).exists():
        # Copy the main pack file
        src = Path(pack["source"])
        dst = ai_rules_dir / f"{pack_name}.yml"
        shutil.copy2(src, dst)
    else:
        # Try to find pack file in packs directory
        pack_file = _packs_dir() / f"{pack_name}.yml"
        if pack_file.exists():
            dst = ai_rules_dir / f"{pack_name}.yml"
            shutil.copy2(pack_file, dst)
        else:
            print(f"not found: {pack_name}")
            return

    print(f"✅ Installed: {pack_name}")


def cmd_search(args: argparse.Namespace) -> None:
    """Search rule packs by keyword."""
    reg = _load_registry()
    query = args.query.lower()
    found = []
    for pack_id, info in reg.get("packs", {}).items():
        if query in pack_id.lower() or query in info.get("description", "").lower():
            found.append({pack_id: info})
            if not getattr(args, "json", False):
                print(f"Found: {pack_id} (v{info['version']}): {info.get('description', 'No description')}")
    if not found:
        if getattr(args, "json", False):
            print(json.dumps({}, ensure_ascii=False))
        else:
            print("No packs matching")
    elif getattr(args, "json", False):
        # Convert list of single-key dicts to a single dict
        result = {}
        for item in found:
            result.update(item)
        print(json.dumps(result, ensure_ascii=False))


def cmd_info(args: argparse.Namespace) -> None:
    """Show info about a rule pack."""
    reg = _load_registry()
    pack_name = getattr(args, "pack", getattr(args, "name", None))
    pack = reg.get("packs", {}).get(pack_name)
    if not pack:
        if getattr(args, "json", False):
            print(json.dumps({}, ensure_ascii=False))
        else:
            print(f"not found: {pack_name}")
        return

    if getattr(args, "json", False):
        # Output as {pack_name: pack_info}
        print(json.dumps({pack_name: pack}, ensure_ascii=False))
        return

    print(f"Name: {pack_name}")
    print(f"Version: {pack['version']}")
    print(f"Description: {pack.get('description', 'N/A')}")
    print(f"Rule count: {pack.get('rule_count', 'N/A')}")
    print(f"Published: {pack.get('published', 'N/A')}")
    print(f"Updated: {pack.get('updated', 'N/A')}")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a rule pack from the registry."""
    reg = _load_registry()
    pack_name = getattr(args, "pack", getattr(args, "name", None))
    if pack_name not in reg.get("packs", {}):
        print(f"not found: {pack_name}")
        return

    # Also delete pack file if exists
    pack_file = _packs_dir() / f"{pack_name}.yml"
    if pack_file.exists():
        pack_file.unlink()

    del reg["packs"][pack_name]
    _save_registry(reg)
    print(f"✅ Removed: {pack_name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rule Registry - Central registry for rule packs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # init
    p = subparsers.add_parser("init", help="初始化注册表")
    p.set_defaults(func=cmd_init)

    # list
    p = subparsers.add_parser("list", help="列出所有规则包")
    p.set_defaults(func=cmd_list)

    # publish
    p = subparsers.add_parser("publish", help="发布规则包")
    p.add_argument("file", help="规则包 YAML 文件")
    p.add_argument("--name", help="规则包名称 (默认: 文件名)")
    p.add_argument("--version", help="版本号 (默认: 1.0.0)")
    p.add_argument("--description", help="规则包描述")
    p.add_argument("--tags", help="标签 (逗号分隔)")
    p.set_defaults(func=cmd_publish)

    # install
    p = subparsers.add_parser("install", help="安装规则包到项目")
    p.add_argument("name", help="规则包名称")
    p.add_argument("--dest", default=".", help="目标目录")
    p.set_defaults(func=cmd_install)

    # search
    p = subparsers.add_parser("search", help="搜索规则包")
    p.add_argument("query", help="搜索关键词")
    p.set_defaults(func=cmd_search)

    # info
    p = subparsers.add_parser("info", help="查看规则包详情")
    p.add_argument("name", help="规则包名称")
    p.set_defaults(func=cmd_info)

    # remove
    p = subparsers.add_parser("remove", help="移除规则包")
    p.add_argument("name", help="规则包名称")
    p.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    try:
        args.func(args)
        return 0
    except Exception as e:
        handle_error(e)
        return 1


# Backward compatibility exports for tests
__all__ = [
    "_load_registry",
    "_save_registry",
    "cmd_info",
    "cmd_init",
    "cmd_install",
    "cmd_list",
    "cmd_publish",
    "cmd_remove",
    "cmd_search",
    "init_registry",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
