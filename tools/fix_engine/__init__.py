"""
ADG Custom Fix Engine - AST-level automatic code fixes.

Usage:
    from tools.fix_engine import FixEngine
    engine = FixEngine()
    result = engine.fix_file(Path("main.py"))
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from tools.scripts.adg_cli import Issue, FIX_RULES


# ─────────────────────────────────────────────────────────────
# Custom Fix Patterns (loaded from YAML)
# ─────────────────────────────────────────────────────────────

_FIXES_FILE = Path(__file__).parent / "fixes.yml"


def _load_fixes() -> dict[str, dict[str, Any]]:
    """Load custom fix patterns from the external YAML file."""
    with open(_FIXES_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


CUSTOM_FIXES: dict[str, dict[str, Any]] = _load_fixes()


class FixEngine:
    """Extensible code fix engine with custom rules."""

    def __init__(self, extra_fixes: dict[str, dict[str, Any]] | None = None):
        self.fixes: dict[str, dict[str, Any]] = dict(CUSTOM_FIXES)
        if extra_fixes:
            for lang, fixes in extra_fixes.items():
                if lang not in self.fixes:
                    self.fixes[lang] = {}
                self.fixes[lang].update(fixes)

    def get_fixes_for_language(self, language: str) -> dict[str, dict[str, Any]]:
        """Get all available fixes for a language."""
        return self.fixes.get(language, {})

    def fix_content(
        self,
        content: str,
        language: str,
        rule_ids: list[str] | None = None,
        dry_run: bool = False,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Apply fixes to code content.

        Returns:
            Tuple of (fixed_content, applied_fixes)
        """
        fixes = self.fixes.get(language, {})
        applied = []
        fixed = content

        for rule_id, fix_info in fixes.items():
            if rule_ids and rule_id not in rule_ids:
                continue

            pattern = fix_info.get("pattern", "")
            replacement = fix_info.get("replacement", "")
            import_needed = fix_info.get("import_needed")

            if not pattern:
                continue

            # Check if pattern matches
            matches = list(re.finditer(pattern, fixed))
            if not matches:
                continue

            # Apply fix
            if not dry_run:
                new_content = re.sub(pattern, replacement, fixed)

                # Add import if needed
                if import_needed and import_needed not in new_content:
                    if fix_info.get("import_position") == "top":
                        # Add after shebang/encoding
                        lines = new_content.splitlines(keepends=True)
                        insert_pos = 0
                        for i, line in enumerate(lines):
                            if line.startswith("#!") or line.startswith("# -*-"):
                                insert_pos = i + 1
                            elif line.startswith('"""') or line.startswith("'''"):
                                # Skip docstring
                                if lines.count(line) > 1:
                                    insert_pos = i + 1
                                break
                            elif line.strip() == "":
                                insert_pos = i + 1
                                break
                            else:
                                break

                        lines.insert(insert_pos, import_needed + "\n\n")
                        new_content = "".join(lines)

                    fixed = new_content

            applied.append(
                {
                    "rule_id": rule_id,
                    "description": fix_info.get("description", ""),
                    "matches": len(matches),
                    "pattern": pattern,
                    "replacement": replacement,
                }
            )

        return fixed, applied

    def fix_file(
        self,
        file_path: str | Path,
        language: str | None = None,
        rule_ids: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Fix a single file.

        Returns:
            Dict with fix results
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        # Detect language from extension
        if language is None:
            ext_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".jsx": "javascript",
                ".rs": "rust",
            }
            language = ext_map.get(path.suffix.lower())

        if not language or language not in self.fixes:
            return {"success": False, "error": f"No fixes available for {language}"}

        content = path.read_text(encoding="utf-8", errors="ignore")
        fixed_content, applied = self.fix_content(content, language, rule_ids, dry_run)

        if not dry_run and applied:
            path.write_text(fixed_content, encoding="utf-8")

        return {
            "success": True,
            "file": str(path),
            "language": language,
            "fixes_applied": len(applied),
            "fixes": applied,
            "dry_run": dry_run,
        }

    def fix_directory(
        self,
        dir_path: str | Path,
        language: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Fix all files in a directory.

        Returns:
            Dict with overall fix results
        """
        target = Path(dir_path)
        if not target.exists():
            return {"success": False, "error": f"Directory not found: {target}"}

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".rs": "rust",
        }

        total_fixed = 0
        total_files = 0
        results = []

        files_to_check = list(target.rglob("*"))
        for fp in files_to_check:
            if not fp.is_file():
                continue
            if any(skip in fp.parts for skip in ["node_modules", ".git", "target", "__pycache__"]):
                continue

            file_lang = language or ext_map.get(fp.suffix.lower())
            if not file_lang:
                continue

            result = self.fix_file(fp, file_lang, dry_run=dry_run)
            if result.get("success") and result["fixes_applied"] > 0:
                total_fixed += result["fixes_applied"]
                results.append(result)
            total_files += 1

        return {
            "success": True,
            "files_checked": total_files,
            "files_modified": len(results),
            "total_fixes": total_fixed,
            "dry_run": dry_run,
            "details": results,
        }


# ─────────────────────────────────────────────────────────────
# User Custom Fix Registration
# ─────────────────────────────────────────────────────────────


def load_custom_fixes(project_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load custom fixes from .adg/fixes.yml."""
    config_file = Path(project_dir) / ".adg" / "fixes.yml"
    if not config_file.exists():
        return {}

    try:
        data = yaml.safe_load(config_file.read_text()) or {}
        return data.get("fixes", {})
    except Exception:
        return {}


def save_custom_fix(
    project_dir: str | Path,
    language: str,
    rule_id: str,
    pattern: str,
    replacement: str,
    description: str = "",
) -> bool:
    """Save a custom fix rule to .adg/fixes.yml."""
    config_dir = Path(project_dir) / ".adg"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "fixes.yml"

    existing: dict = {}
    if config_file.exists():
        try:
            existing = yaml.safe_load(config_file.read_text()) or {}
        except Exception:
            pass

    if "fixes" not in existing:
        existing["fixes"] = {}
    if language not in existing["fixes"]:
        existing["fixes"][language] = {}

    existing["fixes"][language][rule_id] = {
        "pattern": pattern,
        "replacement": replacement,
        "description": description,
    }

    config_file.write_text(yaml.dump(existing, default_flow_style=False))
    return True
