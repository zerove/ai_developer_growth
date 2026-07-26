"""
ADG Multi-project Support - Monorepo and cross-project governance.

Usage:
    from tools.multiproject import MonorepoChecker
    checker = MonorepoChecker(root_dir)
    results = checker.check_all()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli import (
    check_directory,
    detect_language,
    load_rules_for_language,
)


class MonorepoChecker:
    """Check governance across multiple projects in a monorepo."""

    def __init__(
        self,
        root_dir: str | Path,
        project_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.root = Path(root_dir)
        self.project_patterns = project_patterns or [
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "build.gradle",
            "pom.xml",
            "Gemfile",
        ]
        self.exclude_patterns = exclude_patterns or [
            "node_modules",
            ".git",
            "target",
            "__pycache__",
            "venv",
            ".venv",
            "dist",
            "build",
        ]

    def discover_projects(self) -> list[dict[str, Any]]:
        """Discover all projects in the monorepo."""
        projects = []

        # Check root
        for pattern in self.project_patterns:
            if (self.root / pattern).exists():
                detected = detect_language(self.root)
                projects.append(
                    {
                        "path": str(self.root),
                        "name": self.root.name,
                        "language": detected.get("language", "unknown"),
                        "framework": detected.get("framework"),
                        "config_file": pattern,
                    }
                )
                break

        # Check subdirectories
        for subdir in self.root.iterdir():
            if not subdir.is_dir():
                continue
            if any(ex in subdir.parts for ex in self.exclude_patterns):
                continue

            for pattern in self.project_patterns:
                if (subdir / pattern).exists():
                    detected = detect_language(subdir)
                    projects.append(
                        {
                            "path": str(subdir),
                            "name": subdir.name,
                            "language": detected.get("language", "unknown"),
                            "framework": detected.get("framework"),
                            "config_file": pattern,
                        }
                    )
                    break

        # Check nested (2 levels deep)
        for subdir in self.root.iterdir():
            if not subdir.is_dir():
                continue
            if any(ex in subdir.parts for ex in self.exclude_patterns):
                continue

            for nested in subdir.iterdir():
                if not nested.is_dir():
                    continue
                if any(ex in nested.parts for ex in self.exclude_patterns):
                    continue

                for pattern in self.project_patterns:
                    if (nested / pattern).exists():
                        detected = detect_language(nested)
                        projects.append(
                            {
                                "path": str(nested),
                                "name": nested.name,
                                "language": detected.get("language", "unknown"),
                                "framework": detected.get("framework"),
                                "config_file": pattern,
                            }
                        )
                        break

        return projects

    def check_project(self, project: dict[str, Any]) -> dict[str, Any]:
        """Check governance for a single project."""
        project_path = Path(project["path"])
        language = project["language"]
        rules = load_rules_for_language(language)
        issues = check_directory(project_path, rules)

        return {
            "project": project["name"],
            "path": project["path"],
            "language": language,
            "framework": project.get("framework"),
            "issues": [i.to_dict() for i in issues],
            "summary": {
                "error": sum(1 for i in issues if i.severity == "error"),
                "warning": sum(1 for i in issues if i.severity == "warning"),
                "info": sum(1 for i in issues if i.severity == "info"),
                "total": len(issues),
            },
            "files_checked": len(set(i.file for i in issues)),
        }

    def check_all(self) -> dict[str, Any]:
        """Check all discovered projects."""
        projects = self.discover_projects()
        results = []
        total_errors = 0
        total_warnings = 0

        for project in projects:
            result = self.check_project(project)
            results.append(result)
            total_errors += result["summary"]["error"]
            total_warnings += result["summary"]["warning"]

        return {
            "root": str(self.root),
            "projects_found": len(projects),
            "results": results,
            "total_summary": {
                "error": total_errors,
                "warning": total_warnings,
                "passed": total_errors == 0,
            },
        }

    def generate_report(self, results: dict[str, Any], output_format: str = "text") -> str:
        """Generate a report from check results."""
        if output_format == "json":
            return json.dumps(results, indent=2)

        lines = [
            "ADG Monorepo Governance Report",
            "=" * 60,
            f"Root: {results['root']}",
            f"Projects: {results['projects_found']}",
            "",
        ]

        for result in results["results"]:
            status = "✅" if result["summary"]["error"] == 0 else "❌"
            lines.append(f"{status} {result['project']} ({result['language']})")
            lines.append(
                f"   Errors: {result['summary']['error']} | Warnings: {result['summary']['warning']} | Files: {result['files_checked']}"
            )

        lines.extend(
            [
                "",
                "-" * 60,
                f"Total errors: {results['total_summary']['error']}",
                f"Total warnings: {results['total_summary']['warning']}",
                f"Quality gate: {'✅ PASSED' if results['total_summary']['passed'] else '❌ FAILED'}",
            ]
        )

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Cross-project Rule Sync
# ─────────────────────────────────────────────────────────────


def sync_rules_across_projects(
    source_project: str | Path,
    target_projects: list[str | Path],
) -> dict[str, Any]:
    """Sync custom rules from one project to others."""
    source = Path(source_project)
    source_config = source / ".adg" / "rules.yml"

    if not source_config.exists():
        return {"success": False, "error": "Source project has no ADG config"}

    import yaml

    source_rules = yaml.safe_load(source_config.read_text()) or {}
    results = []

    for target in target_projects:
        target_path = Path(target)
        target_config = target_path / ".adg" / "rules.yml"
        target_path.mkdir(parents=True, exist_ok=True)

        existing: dict = {}
        if target_config.exists():
            try:
                existing = yaml.safe_load(target_config.read_text()) or {}
            except Exception:
                pass

        # Merge rules
        source_custom = source_rules.get("custom_rules", [])
        target_custom = existing.get("custom_rules", [])
        existing_ids = {r.get("id") for r in target_custom}

        new_rules = [r for r in source_custom if r.get("id") not in existing_ids]
        target_custom.extend(new_rules)

        existing["custom_rules"] = target_custom
        target_config.write_text(yaml.dump(existing, default_flow_style=False))

        results.append(
            {
                "target": str(target),
                "rules_synced": len(new_rules),
                "total_rules": len(target_custom),
            }
        )

    return {"success": True, "results": results}
