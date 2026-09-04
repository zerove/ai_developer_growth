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
    # 从 args.path 推断项目目录 (与 cmd_recommend 一致)，默认 "." 避免修改意外路径
    project_dir = getattr(args, "path", None) or "."

    if cmd == "list":
        packs = list_packs()
        print(format_packs_list(packs))
    elif cmd == "search":
        packs = search_packs(args.query)
        print(format_packs_list(packs))
    elif cmd == "install":
        result = install_pack(args.pack_id, project_dir=project_dir, language=args.lang)
        if result["success"]:
            print(f"✅ Installed pack: {result['pack']}")
            print(f"   Rules installed: {result['rules_installed']}")
            print(f"   Total rules: {result['total_rules']}")
        else:
            print(f"❌ Failed: {result['error']}")
            return 1
    elif cmd == "uninstall":
        result = uninstall_pack(args.pack_id, project_dir=project_dir)
        if result["success"]:
            print(f"✅ Uninstalled pack: removed {result['removed']} rules")
        else:
            print(f"❌ Failed: {result['error']}")
            return 1
    else:
        print("Usage: adg marketplace {list|search|install|uninstall}")
        return 1
    return 0
