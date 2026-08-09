"""Rule catalog: pack definitions, search, install, validate, and export.

Core business logic extracted from rule_marketplace.py for reuse
by other tools (hooks_runner, quality-gate, etc.).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import framework_dir

# ──────────────────────────────────────────────────────────
# Built-in pack definitions
# ──────────────────────────────────────────────────────────

BUILTIN_PACKS: dict[str, dict[str, Any]] = {
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
# Search / matching
# ──────────────────────────────────────────────────────────

_CATEGORIES = ["anti_patterns", "naming_conventions", "complexity"]


def matches(rule: dict[str, Any], query: str) -> bool:
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


def _search_common_rules(query: str) -> list[dict[str, Any]]:
    """Search common rules (security)."""
    results: list[dict[str, Any]] = []
    fw = framework_dir()
    common_file = fw / "common" / "security.yml"
    if common_file.exists():
        with open(common_file) as f:
            data = yaml.safe_load(f) or {}
        for rule in data.get("anti_patterns", []):
            if matches(rule, query):
                results.append({"pack": "security", **rule})
    return results


def _search_language_rules(query: str) -> list[dict[str, Any]]:
    """Search language-specific rules."""
    results: list[dict[str, Any]] = []
    fw = framework_dir()
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
                for category in _CATEGORIES:
                    for rule in data.get(category, []):
                        if matches(rule, query):
                            results.append({"pack": lang_dir.name, "category": category, **rule})
    return results


def _search_framework_rules(query: str) -> list[dict[str, Any]]:
    """Search framework-specific rules."""
    results: list[dict[str, Any]] = []
    fw = framework_dir()
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
                for category in _CATEGORIES:
                    for rule in data.get(category, []):
                        if matches(rule, query):
                            results.append({"pack": fw_dir.name, "category": category, **rule})
    return results


def search_rules(query: str) -> list[dict[str, Any]]:
    """Search all rule sources for rules matching a query.

    Returns list of dicts with pack, category, and rule data.
    """
    results: list[dict[str, Any]] = []
    results.extend(_search_common_rules(query))
    results.extend(_search_language_rules(query))
    results.extend(_search_framework_rules(query))
    return results


# ──────────────────────────────────────────────────────────
# Pack operations
# ──────────────────────────────────────────────────────────


def get_pack_info(pack_id: str) -> dict[str, Any] | None:
    """Get info about a pack. Returns None if not found."""
    return BUILTIN_PACKS.get(pack_id)


def get_pack_source(pack_id: str) -> Path | None:
    """Get the resolved source path for a pack."""
    info = BUILTIN_PACKS.get(pack_id)
    if not info:
        return None
    path: Path = framework_dir() / info["source"]
    return path


def install_pack(pack_id: str, project_dir: Path, dry_run: bool = False) -> list[Path]:
    """Install a rule pack to .ai-rules/. Returns list of installed file paths."""
    info = BUILTIN_PACKS.get(pack_id)
    if not info:
        raise ValueError(f"Unknown pack: {pack_id}")

    target_dir = project_dir / ".ai-rules"
    src = framework_dir() / info["source"]

    if dry_run:
        return []

    target_dir.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []

    if src.is_file():
        dest = target_dir / src.name
        shutil.copy2(src, dest)
        installed.append(dest)
    elif src.is_dir():
        for yml in src.glob("*.yml"):
            dest = target_dir / f"{pack_id}-{yml.name}"
            shutil.copy2(yml, dest)
            installed.append(dest)

    return installed


def validate_rules(rules_dir: Path) -> tuple[int, int, list[str]]:
    """Validate all YAML rules in a directory.

    Returns (total_rules, error_count, error_messages).
    """
    total_rules = 0
    errors = 0
    messages: list[str] = []

    if not rules_dir.exists():
        return 0, 0, [f"Directory not found: {rules_dir}"]

    for yml in sorted(rules_dir.glob("*.yml")):
        try:
            with open(yml) as f:
                data = yaml.safe_load(f)
            if not data:
                messages.append(f"{yml.name}: empty or invalid YAML")
                errors += 1
                continue

            for category in _CATEGORIES:
                for rule in data.get(category, []):
                    if not rule.get("id"):
                        messages.append(f"{yml.name}: rule missing 'id'")
                        errors += 1
                    if not rule.get("pattern") and category in ["anti_patterns", "complexity"]:
                        messages.append(f"{yml.name}/{rule.get('id', '?')}: missing 'pattern'")
                        errors += 1
                    if not rule.get("message"):
                        messages.append(f"{yml.name}/{rule.get('id', '?')}: missing 'message'")
                        errors += 1
                    total_rules += 1
        except yaml.YAMLError as e:
            messages.append(f"{yml.name}: YAML parse error: {e}")
            errors += 1

    return total_rules, errors, messages


def export_rules(rules_dir: Path, output: Path) -> tuple[int, dict[str, Any]]:
    """Export rules from .ai-rules/ to a single YAML file.

    Returns (rule_count, combined_dict).
    """
    combined: dict[str, Any] = {"anti_patterns": [], "naming_conventions": [], "complexity": []}

    for yml in sorted(rules_dir.glob("*.yml")):
        with open(yml) as f:
            data = yaml.safe_load(f) or {}
        for category in combined:
            combined[category].extend(data.get(category, []))

    total = sum(len(v) for v in combined.values())
    return total, combined
