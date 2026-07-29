"""Rule loading, caching, and merging for language rules."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from tools.scripts._common import rules_dir
from tools.scripts.rules_engine.logger import logger

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
            result: dict[str, Any] = json.loads(_DISK_CACHE_FILE.read_text())
            return result
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


def _rules_hash(language: str, framework_dir: Path | None = None) -> str:
    """Hash of rule file for cache invalidation."""
    if framework_dir is None:
        framework_dir = rules_dir()
    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"
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
            result: dict[str, str] = json.loads(cache_file.read_text())
            return result
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
    rh = _rules_hash(language, framework_dir)
    cache_key = f"{language}:{rh}"
    if cache_key in _RULE_CACHE:
        return _RULE_CACHE[cache_key]

    # Check disk cache
    disk_cache = _load_disk_cache()
    if cache_key in disk_cache:
        _RULE_CACHE[cache_key] = disk_cache[cache_key]
        cached: dict[str, Any] = disk_cache[cache_key]
        return cached

    try:
        import yaml
    except ImportError:
        # PyYAML not available - use universal rules
        logger.info("Warning: PyYAML not installed. Using universal rules.", file=sys.stderr)
        return _load_universal_rules(framework_dir)

    if framework_dir is None:
        framework_dir = rules_dir()

    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    if not rule_path.exists():
        # Language not in our database - load universal rules instead
        logger.info(f"No specific rules for '{language}', using universal quality rules.", file=sys.stderr)
        return _load_universal_rules(framework_dir)

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
    """Load custom rules from multiple sources with inheritance.

    Priority order (later overrides earlier):
    1. ~/.config/adg/rules.yml (user global config)
    2. .adg/rules.yml (project-level config)
    3. .ai-rules/*.yml (legacy directory-based config)

    Rules with the same ID override built-in rules.
    """
    custom: dict[str, Any] = {"anti_patterns": [], "naming": {}, "thresholds": {}}

    # Source 1: User global config (~/.config/adg/rules.yml)
    global_config = Path.home() / ".config" / "adg" / "rules.yml"
    if global_config.is_file():
        _load_single_custom_file(global_config, custom)

    # Source 2: Project-level .adg/rules.yml
    project_adg_rules = project_dir / ".adg" / "rules.yml"
    if project_adg_rules.is_file():
        _load_single_custom_file(project_adg_rules, custom)

    # Source 3: Legacy .ai-rules/*.yml directory
    ai_rules_dir = project_dir / ".ai-rules"
    if ai_rules_dir.is_dir():
        for rule_file in sorted(ai_rules_dir.glob("*.yml")):
            _load_single_custom_file(rule_file, custom)

    return custom


def _load_single_custom_file(rule_file: Path, custom: dict[str, Any]) -> None:
    """Load a single custom rule file and merge into custom dict."""
    try:
        import yaml
    except ImportError:
        logger.info("Warning: PyYAML not installed. Custom rules skipped.", file=sys.stderr)
        return

    try:
        with open(rule_file) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return

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


def _merge_anti_patterns(
    base_patterns: list[dict[str, Any]], custom_patterns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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


def _load_common_rules(framework_dir: Path | None = None) -> dict[str, Any]:
    """Load common cross-language rules from common/security.yml."""
    if framework_dir is None:
        framework_dir = rules_dir()
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


def _load_universal_rules(framework_dir: Path | None = None) -> dict[str, Any]:
    """Load universal quality rules for languages without specific rule sets.

    These rules apply to ANY programming language — they catch common
    cross-language issues like hardcoded secrets, empty catch blocks,
    SQL injection patterns, and resource leaks.

    Returns universal rules merged with common cross-language rules.
    """
    if framework_dir is None:
        framework_dir = rules_dir()
    result: dict[str, Any] = {"anti_patterns": [], "thresholds": {}, "naming": {}}

    # 1. Load universal rules
    universal_path = framework_dir / "common" / "universal.yml"
    if universal_path.exists():
        try:
            import yaml
            with open(universal_path) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                result = data
        except Exception:
            pass

    # 2. Load and merge common cross-language rules (security, type, error)
    common = _load_common_rules(framework_dir)
    if common:
        result = _merge_rules(result, common)

    return result


def load_rules_for_language(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load rules for a language, merging with common security rules.

    Common rules come from common/security.yml (loaded by load_rules()).
    This function no longer calls security_patterns.py separately —
    all cross-language rules are consolidated in common/security.yml.
    """
    return load_rules(language, framework_dir)


def load_domain_rules(project_path: Path, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load domain-specific rules based on project configuration.

    Reads .adg/config.yml for `domains:` field and loads matching
    rule files from ai-dev-framework/domains/{domain}.yml.

    Args:
        project_path: Project root directory.
        framework_dir: Framework root directory.

    Returns:
        Dict with 'anti_patterns' key containing domain rules.
    """
    result: dict[str, Any] = {"anti_patterns": []}

    fd = framework_dir or rules_dir()
    domains_dir = fd / "domains"

    # Find project config (.adg/config.yml, .jcode/config.yml, pyproject.toml)
    config_sources = [
        project_path / ".adg" / "config.yml",
        project_path / ".jcode" / "config.yml",
    ]
    active_domains: list[str] = []

    for config_path in config_sources:
        if config_path.exists():
            try:
                import yaml
                data = yaml.safe_load(config_path.read_text())
                active_domains = data.get("domains", [])
                break
            except Exception:
                pass

    for domain in active_domains:
        rule_file = domains_dir / f"{domain}.yml"
        if rule_file.exists():
            try:
                import yaml
                data = yaml.safe_load(rule_file.read_text())
                for p in data.get("anti_patterns", []):
                    result["anti_patterns"].append(p)
            except Exception:
                pass

    return result


def get_language_rules(language: str) -> dict[str, Any]:
    """Get rules for a language (cached)."""
    return load_rules_for_language(language)
