"""Rule loading, caching, and merging for language rules."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from pathlib import Path as PathLib

sys.path.insert(0, str(PathLib(__file__).parent.parent))

from typing import Any

from _common import rules_dir

# ──────────────────────────────────────────────────────────
# Rule cache
# ──────────────────────────────────────────────────────────

_RULE_CACHE: dict[str, dict[str, Any]] = {}
_FILE_HASH_CACHE: dict[str, str] = {}

# Disk cache path
_DISK_CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "rules_engine"
_DISK_CACHE_FILE = _DISK_CACHE_DIR / "rules_cache.json"


def _file_hash(filepath: Path) -> str:
    """Quick content hash for incremental checks."""
    try:
        content = filepath.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except OSError:
        return ""


def _load_disk_cache() -> dict[str, Any]:
    """Load rules from disk cache."""
    if _DISK_CACHE_FILE.exists():
        try:
            return json.loads(_DISK_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_disk_cache(cache: dict[str, Any]) -> None:
    """Save rules to disk cache."""
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _DISK_CACHE_FILE.write_text(json.dumps(cache))
    except OSError:
        pass


def _rules_hash(language: str) -> str:
    """Hash of rule file for cache invalidation."""
    rule_path = (
        Path(__file__).parent.parent.parent
        / "ai-dev-framework"
        / "languages"
        / language
        / "rules.d"
        / "anti_patterns.yml"
    )
    if not rule_path.exists():
        return ""
    try:
        return hashlib.sha256(rule_path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _load_cache(cache_file: Path) -> dict[str, str]:
    """Load file hash cache from disk."""
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache_file: Path, cache: dict[str, str]) -> None:
    """Save file hash cache to disk."""
    try:
        cache_file.write_text(json.dumps(cache))
    except OSError:
        pass


def load_rules(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load YAML rules for a given language with caching."""
    # Check in-memory cache
    rh = _rules_hash(language)
    cache_key = f"{language}:{rh}"
    if cache_key in _RULE_CACHE:
        return _RULE_CACHE[cache_key]

    # Check disk cache
    disk_cache = _load_disk_cache()
    if cache_key in disk_cache:
        _RULE_CACHE[cache_key] = disk_cache[cache_key]
        return disk_cache[cache_key]

    try:
        import yaml
    except ImportError:
        # PyYAML not available - use embedded rules
        print("Warning: PyYAML not installed. Using embedded rules.", file=sys.stderr)
        return _get_embedded_rules(language)

    if framework_dir is None:
        framework_dir = rules_dir()

    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    if not rule_path.exists():
        print(f"Warning: Rules not found at {rule_path}, using embedded rules.", file=sys.stderr)
        return _get_embedded_rules(language)

    with open(rule_path) as f:
        data = yaml.safe_load(f)

    result = data if isinstance(data, dict) else {}

    # Load common cross-language rules
    common = _load_common_rules(framework_dir)
    if common:
        result = _merge_rules(result, common)

    # Cache the result
    _RULE_CACHE[cache_key] = result

    # Save to disk cache
    disk_cache[cache_key] = result
    _save_disk_cache(disk_cache)

    return result


def load_custom_rules(project_dir: Path) -> dict[str, Any]:
    """Load custom rules from .ai-rules/*.yml in the project directory.

    Custom rules extend (not replace) built-in rules.
    Rules with the same ID override built-in rules.
    """
    custom: dict[str, Any] = {"anti_patterns": [], "naming": {}, "thresholds": {}}
    rules_dir_path = project_dir / ".ai-rules"

    if not rules_dir_path.is_dir():
        return custom

    try:
        import yaml
    except ImportError:
        print("Warning: PyYAML not installed. Custom rules skipped.", file=sys.stderr)
        return custom

    for rule_file in sorted(rules_dir_path.glob("*.yml")):
        try:
            with open(rule_file) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue

            # Merge anti_patterns (override by ID)
            new_patterns = data.get("anti_patterns", [])
            custom["anti_patterns"].extend(new_patterns)

            # Merge naming rules
            if "naming" in data:
                custom["naming"].update(data["naming"])

            # Merge thresholds (override)
            if "thresholds" in data:
                custom["thresholds"].update(data["thresholds"])

        except Exception as e:
            print(f"Warning: Failed to load {rule_file}: {e}", file=sys.stderr)

    return custom


def _merge_anti_patterns(base_patterns: list[dict], custom_patterns: list[dict]) -> list[dict]:
    """Merge anti-patterns: custom overrides by ID, then appends new ones."""
    if not custom_patterns:
        return base_patterns

    base_ids = {p["id"] for p in base_patterns}
    overridden = []
    new_only = []
    for cp in custom_patterns:
        if cp.get("id") in base_ids:
            overridden.append(cp)
        else:
            new_only.append(cp)

    merged_patterns = []
    for p in base_patterns:
        match = next((cp for cp in overridden if cp["id"] == p["id"]), None)
        if match:
            if "severity_override" in match:
                p = dict(p)
                p["severity"] = match["severity_override"]
                merged_patterns.append(p)
            else:
                merged_patterns.append(match)
        else:
            merged_patterns.append(p)
    merged_patterns.extend(new_only)
    return merged_patterns


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules. Custom overrides by ID.

    Supports two modes:
    - Full replacement: custom rule with same ID replaces the entire base rule
    - Severity override: custom rule with severity_override only changes severity
    """
    merged = dict(base)

    # Merge anti_patterns
    merged["anti_patterns"] = _merge_anti_patterns(
        merged.get("anti_patterns", []),
        custom.get("anti_patterns", []),
    )

    # Merge naming
    if custom.get("naming"):
        merged.setdefault("naming", {}).update(custom["naming"])

    # Merge thresholds
    if custom.get("thresholds"):
        merged.setdefault("thresholds", {}).update(custom["thresholds"])

    return merged


# ──────────────────────────────────────────────────────────
# Cross-language common rules
# ──────────────────────────────────────────────────────────


def _load_common_rules(framework_dir: Path) -> dict[str, Any]:
    """Load common cross-language rules from common/security.yml."""
    common_path = framework_dir / "common" / "security.yml"
    if not common_path.exists():
        return {}

    try:
        import yaml

        with open(common_path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_embedded_rules(language: str) -> dict[str, Any]:
    """Fallback embedded rules when YAML files are unavailable."""
    common_anti_patterns: list[dict[str, Any]] = [
        {
            "id": f"{language[:2]}-eval-exec",
            "name": "Use of eval/exec",
            "severity": "error",
            "category": "security",
            "pattern": r"\beval\s*\(|\bexec\s*\(",
            "message": "eval/exec are security risks",
            "fix_hint": "Find a safer alternative",
        },
        {
            "id": f"{language[:2]}-hardcoded-secret",
            "name": "Hardcoded secret",
            "severity": "error",
            "category": "security",
            "pattern": r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            "message": "Hardcoded secrets are a security vulnerability",
            "fix_hint": "Use environment variables",
        },
    ]
    return {"anti_patterns": common_anti_patterns, "thresholds": {}, "naming": {}}


def load_rules_for_language(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load rules for a language, merging with common security rules."""
    rules = load_rules(language, framework_dir)
    # Add cross-language security rules
    from .security_patterns import get_security_rules

    security = get_security_rules(language)
    rules = _merge_rules(rules, security)
    return rules


def get_language_rules(language: str) -> dict[str, Any]:
    """Get rules for a language (cached)."""
    return load_rules_for_language(language)
