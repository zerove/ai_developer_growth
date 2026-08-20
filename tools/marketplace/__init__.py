"""
ADG Plugin Marketplace - Community rule packs.

Usage:
    adg install community/security-pack
    adg marketplace search security
    adg marketplace list
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ─────────────────────────────────────────────────────────────
# Built-in Rule Packs (loaded from YAML)
# ─────────────────────────────────────────────────────────────

_PACKS_FILE = Path(__file__).parent / "packs.yml"


def _load_packs() -> dict[str, dict[str, Any]]:
    """Load built-in rule packs from the external YAML file."""
    with open(_PACKS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


BUILTIN_PACKS: dict[str, dict[str, Any]] = _load_packs()


# ─────────────────────────────────────────────────────────────
# Marketplace Operations
# ─────────────────────────────────────────────────────────────


def list_packs() -> list[dict[str, Any]]:
    """List all available rule packs."""
    packs = []
    for pack_id, pack in BUILTIN_PACKS.items():
        total_rules = sum(len(rules) for rules in pack["rules"].values())
        packs.append(
            {
                "id": pack_id,
                "name": pack["name"],
                "description": pack["description"],
                "author": pack["author"],
                "version": pack["version"],
                "total_rules": total_rules,
                "languages": list(pack["rules"].keys()),
            }
        )
    return packs


def search_packs(query: str) -> list[dict[str, Any]]:
    """Search rule packs by name or description."""
    query_lower = query.lower()
    return [
        p
        for p in list_packs()
        if query_lower in p["name"].lower()
        or query_lower in p["description"].lower()
        or query_lower in p["id"].lower()
    ]


def install_pack(
    pack_id: str,
    project_dir: str | Path = ".",
    language: str | None = None,
) -> dict[str, Any]:
    """Install a rule pack into a project."""
    pack = BUILTIN_PACKS.get(pack_id)
    if not pack:
        return {"success": False, "error": f"Pack '{pack_id}' not found"}

    project = Path(project_dir)
    adg_dir = project / ".adg"
    adg_dir.mkdir(parents=True, exist_ok=True)

    # Load existing config
    config_file = adg_dir / "rules.yml"
    existing_rules: list[dict[str, Any]] = []
    if config_file.exists():
        try:
            content = config_file.read_text()
            if "custom_rules:" in content:
                data = yaml.safe_load(content)
                existing_rules = data.get("custom_rules", [])
        except Exception:
            # 规则配置损坏时忽略，从零构建
            pass

    # Add new rules
    target_langs = [language] if language else list(pack["rules"].keys())
    new_rules = []
    for lang in target_langs:
        if lang in pack["rules"]:
            for rule in pack["rules"][lang]:
                rule_with_lang = {**rule, "language": lang}
                if not any(r.get("id") == rule["id"] for r in existing_rules):
                    new_rules.append(rule_with_lang)
                    existing_rules.append(rule_with_lang)

    # Write back
    config = {
        "custom_rules": existing_rules,
        "installed_packs": [pack_id],
    }
    config_file.write_text(yaml.dump(config, default_flow_style=False))

    return {
        "success": True,
        "pack": pack_id,
        "rules_installed": len(new_rules),
        "total_rules": len(existing_rules),
    }


def uninstall_pack(
    pack_id: str,
    project_dir: str | Path = ".",
) -> dict[str, Any]:
    """Remove a rule pack from a project."""
    project = Path(project_dir)
    config_file = project / ".adg" / "rules.yml"

    if not config_file.exists():
        return {"success": False, "error": "No config found"}

    try:
        config = yaml.safe_load(config_file.read_text()) or {}
        custom_rules = config.get("custom_rules", [])

        pack = BUILTIN_PACKS.get(pack_id, {})
        pack_rule_ids = set()
        for lang_rules in pack.get("rules", {}).values():
            for rule in lang_rules:
                pack_rule_ids.add(rule["id"])

        new_rules = [r for r in custom_rules if r.get("id") not in pack_rule_ids]
        config["custom_rules"] = new_rules
        config["installed_packs"] = [
            p for p in config.get("installed_packs", []) if p != pack_id
        ]

        config_file.write_text(yaml.dump(config, default_flow_style=False))
        return {"success": True, "removed": len(custom_rules) - len(new_rules)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_packs_list(packs: list[dict[str, Any]]) -> str:
    """Format pack list for display."""
    if not packs:
        return "No packs found."

    lines = ["Available Rule Packs:", ""]
    for p in packs:
        lines.append(f"  {p['id']:25s} {p['name']}")
        lines.append(f"  {'':25s} {p['description']}")
        lines.append(
            f"  {'':25s} Rules: {p['total_rules']} | Languages: {', '.join(p['languages'])}"
        )
        lines.append("")
    return "\n".join(lines)
