"""RuleEngine Facade: unified entry point for all rule operations.

Provides a single API that wraps the rule_* modules:
- rule_author: create/validate rules
- rule_catalog: discover/install/search rule packs
- rule_registry: publish/install packs
- rule_tracker: record/track effectiveness
- rule_visualize: web UI
- rules_engine: core validation

Usage:
    from tools.scripts.rule_engine import RuleEngine

    engine = RuleEngine()
    results = engine.validate_file("path/to/file.py", "python")
    engine.record_results(results)
    packs = engine.search_packs("security")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class RuleEngine:
    """Unified facade for rule operations."""

    def __init__(self) -> None:
        self._rules_dir: Path | None = None

    @property
    def rules_dir(self) -> Path:
        if self._rules_dir is None:
            from tools.scripts._common import rules_dir

            self._rules_dir = rules_dir()
        return self._rules_dir

    # ── Validation ──────────────────────────────────────────

    def validate_file(self, filepath: str | Path, lang: str) -> dict[str, Any]:
        """Validate a single file against language rules.

        Returns dict with keys: file, language, issues, health_score.
        """
        from tools.scripts.validators.pipeline import validate_file

        result = validate_file(Path(filepath), lang)
        return {
            "file": str(filepath),
            "language": lang,
            "issues": [asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in result.issues],
            "health_score": getattr(result, "health_score", None),
        }

    def validate_directory(self, directory: str | Path, lang: str) -> dict[str, Any]:
        """Validate all files in a directory.

        Returns dict with keys: results, summary.
        """
        from tools.scripts.validators.pipeline import validate_directory

        results = validate_directory(Path(directory), lang)
        total_issues = sum(len(r.issues) for r in results)
        return {
            "results": [
                {
                    "file": str(r.file),
                    "language": r.language,
                    "issues": [asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in r.issues],
                }
                for r in results
            ],
            "summary": {
                "total_files": len(results),
                "total_issues": total_issues,
            },
        }

    # ── Rule Authoring ──────────────────────────────────────

    def init_rules(self, lang: str, force: bool = False) -> None:
        """Initialize rule directory for a language."""
        import argparse

        from tools.scripts.rule_author import cmd_init

        cmd_init(argparse.Namespace(lang=lang, force=force))

    def add_rule(self, lang: str, category: str, rule_id: str, name: str, **kwargs: Any) -> None:
        """Add a rule to a language's rule file."""
        import argparse

        from tools.scripts.rule_author import cmd_add_rule

        cmd_init_ns = argparse.Namespace(
            lang=lang,
            category=category,
            id=rule_id,
            name=name,
            severity=kwargs.get("severity", "warning"),
            message=kwargs.get("message", ""),
            pattern=kwargs.get("pattern"),
            fix_hint=kwargs.get("fix_hint"),
        )
        cmd_add_rule(cmd_init_ns)

    def validate_rule_file(self, filepath: str | Path) -> None:
        """Validate a rule YAML file."""
        import argparse

        from tools.scripts.rule_author import cmd_validate

        cmd_validate(argparse.Namespace(file=str(filepath)))

    # ── Marketplace ─────────────────────────────────────────

    def search_packs(self, query: str) -> list[dict[str, Any]]:
        """Search rule packs by keyword."""
        from tools.scripts.rule_catalog import search_rules

        return search_rules(query.lower())

    def get_pack_info(self, pack_id: str) -> dict[str, Any] | None:
        """Get info about a rule pack."""
        from tools.scripts.rule_catalog import get_pack_info

        return get_pack_info(pack_id)

    def install_pack(self, pack_id: str, project_dir: str | Path, dry_run: bool = False) -> list[Path]:
        """Install a rule pack to a project."""
        from tools.scripts.rule_catalog import install_pack

        return install_pack(pack_id, Path(project_dir), dry_run=dry_run)

    def list_packs(self) -> list[dict[str, Any]]:
        """List all built-in packs."""
        from tools.scripts.rule_catalog import BUILTIN_PACKS

        return [{"id": pid, **info} for pid, info in BUILTIN_PACKS.items()]

    # ── Tracking ────────────────────────────────────────────

    def record_results(self, results: dict[str, Any], project: str = "unknown") -> None:
        """Record validation results for tracking."""
        import json
        from datetime import datetime, timezone

        from tools.scripts.rule_tracker import _count_by_rule, _count_by_severity, _records_file

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project": project,
            "results": results.get("results", []),
            "health_score": results.get("health_score"),
            "summary": {
                "total_files": len(results.get("results", [])),
                "total_issues": sum(len(r.get("issues", [])) for r in results.get("results", [])),
                "by_severity": _count_by_severity(results.get("results", [])),
                "by_rule": _count_by_rule(results.get("results", [])),
            },
        }

        with open(_records_file(), "a") as f:
            f.write(json.dumps(record) + "\n")

    def get_tracking_report(self, days: int | None = None) -> dict[str, Any]:
        """Get effectiveness tracking report."""
        from collections import defaultdict

        from tools.scripts.rule_tracker import _load_records

        records = _load_records(days)
        if not records:
            return {"records": 0, "total_issues": 0}

        total_issues = 0
        rule_counts: dict[str, int] = defaultdict(int)
        for rec in records:
            summary = rec.get("summary", {})
            total_issues += summary.get("total_issues", 0)
            for rule_id, count in summary.get("by_rule", {}).items():
                rule_counts[rule_id] += count

        return {
            "records": len(records),
            "total_issues": total_issues,
            "by_rule": dict(sorted(rule_counts.items(), key=lambda x: -x[1])),
        }

    # ── Visualization ───────────────────────────────────────

    def get_all_rules(self) -> dict[str, dict[str, Any]]:
        """Load all rules organized by language."""
        from tools.scripts.rule_visualize import get_all_rules

        return get_all_rules()

    def start_web_ui(self, port: int = 8080) -> None:
        """Start the rule visualization web server."""
        from tools.scripts.rule_visualize import VisualizeHandler, run_server

        run_server(VisualizeHandler, port=port)


def asdict(obj: Any) -> dict[str, Any]:
    """Convert dataclass to dict, or return as-is if not a dataclass."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f: getattr(obj, f) for f in obj.__dataclass_fields__}
    if isinstance(obj, dict):
        return obj
    return {"value": obj}
