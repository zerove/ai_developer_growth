from __future__ import annotations

import argparse


def cmd_marketplace(args: argparse.Namespace) -> int:
    """Rule pack marketplace operations."""
    from tools.marketplace import (
        format_packs_list,
        install_pack,
        list_packs,
        search_packs,
        uninstall_pack,
    )

    cmd = args.marketplace_command

    if cmd == "list":
        packs = list_packs()
        print(format_packs_list(packs))
    elif cmd == "search":
        packs = search_packs(args.query)
        print(format_packs_list(packs))
    elif cmd == "install":
        result = install_pack(args.pack_id, language=args.lang)
        if result["success"]:
            print(f"✅ Installed pack: {result['pack']}")
            print(f"   Rules installed: {result['rules_installed']}")
            print(f"   Total rules: {result['total_rules']}")
        else:
            print(f"❌ Failed: {result['error']}")
            return 1
    elif cmd == "uninstall":
        result = uninstall_pack(args.pack_id)
        if result["success"]:
            print(f"✅ Uninstalled pack: removed {result['removed']} rules")
        else:
            print(f"❌ Failed: {result['error']}")
            return 1
    else:
        print("Usage: adg marketplace {list|search|install|uninstall}")
        return 1
    return 0
