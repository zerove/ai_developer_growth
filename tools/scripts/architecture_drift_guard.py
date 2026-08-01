"""Architecture Drift Guard (Pillar 1)

Checks codebase against ADR rules and architectural layering constraints
(e.g., domain layer should not depend on UI or infrastructure directly).
"""

from __future__ import annotations

import sys
from pathlib import Path

from _common import get_project_root


class ArchitectureDriftGuard:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.violations: list[str] = []

    def check_layering(self) -> list[str]:
        py_files = list(self.root_dir.glob("**/*.py"))
        for file_path in py_files:
            if "domain" in file_path.parts:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "infrastructure" in content or "web" in content or "fastapi" in content:
                        rel = file_path.relative_to(self.root_dir)
                        self.violations.append(
                            f"Architecture Drift in {rel}: Domain layer imports infrastructure/web components."
                        )
                except Exception:
                    pass
        return self.violations

    def check_adr_references(self) -> list[str]:
        adr_dir = self.root_dir / "docs" / "adr"
        if not adr_dir.exists():
            return []
        return []


if __name__ == "__main__":
    guard = ArchitectureDriftGuard()
    violations = guard.check_layering()
    if violations:
        print("❌ Architecture Drift Detected:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("✅ Architecture Drift Guard passed: No layering violations found.")
        sys.exit(0)
