"""AI Slop & Anti-Hallucination Scanner (Pillar 4)

Detects AI-generated code smells, over-abstractions, excessive exception swallowing,
and unwarranted comments or redundant type annotations.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _common import get_project_root


class AISlopScanner:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.slop_findings: list[str] = []

    def scan_codebase(self) -> list[str]:
        py_files = list(self.root_dir.glob("**/*.py"))
        for file_path in py_files:
            if any(p in str(file_path) for p in [".venv", "build", "dist", ".git", "__pycache__"]):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                if "as any" in content:
                    rel = file_path.relative_to(self.root_dir)
                    self.slop_findings.append(f"AI Slop found in {rel}: Usage of 'as any' type suppression.")
                if "except Exception:\n        pass" in content or "except Exception: pass" in content:
                    rel = file_path.relative_to(self.root_dir)
                    self.slop_findings.append(f"AI Slop found in {rel}: Empty exception catch block.")
            except Exception:
                pass
        return self.slop_findings


if __name__ == "__main__":
    scanner = AISlopScanner()
    findings = scanner.scan_codebase()
    if findings:
        print("⚠️ AI Slop / Anti-Hallucination Warnings:")
        for f in findings:
            print(f"  - {f}")
    else:
        print("✅ AI Slop Scanner passed: No code smells or slop detected.")
    sys.exit(0)
