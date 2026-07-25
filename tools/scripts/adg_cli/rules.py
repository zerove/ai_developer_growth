from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.detect import detect_language, _simple_yaml_parse, _load_yaml
from tools.scripts.adg_cli.core import _get_rules_path, _ADG_HOME, _ADG_SOURCE

def load_rules_for_language(language: str) -> dict[str, Any]:
    """Load anti-pattern rules for a specific language."""
    rules_path = _get_rules_path()
    lang_rules_file = rules_path / "languages" / language / "rules.d" / "anti_patterns.yml"

    lang_rules: dict[str, Any] = {"anti_patterns": []}
    if lang_rules_file.exists():
        lang_rules = _load_yaml(lang_rules_file)

    # Load cross-language security rules
    security_file = rules_path / "common" / "security.yml"
    security_rules: dict[str, Any] = {"anti_patterns": []}
    if security_file.exists():
        security_rules = _load_yaml(security_file)

    # Merge: language-specific + security
    all_patterns = lang_rules.get("anti_patterns", []) + security_rules.get("anti_patterns", [])
    return {"anti_patterns": all_patterns, "language": language}


def load_framework_rules(framework: str) -> dict[str, Any]:
    """Load anti-pattern rules for a specific framework."""
    rules_path = _get_rules_path()
    fw_rules_file = rules_path / "frameworks" / framework / "rules.d" / "anti_patterns.yml"

    if fw_rules_file.exists():
        return _load_yaml(fw_rules_file)
    return {"anti_patterns": []}
