"""JCode Workflow & Tools Synchronization Engine."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def sync_project_workflows(target_dir: str | Path = ".") -> dict[str, Any]:
    """Synchronize JCode workflows, hooks runner, and automation tools into target project."""
    target_path = Path(target_dir).resolve()
    jcode_dir = target_path / ".jcode"
    scripts_dir = target_path / "tools" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    jcode_dir.mkdir(parents=True, exist_ok=True)

    # Source tools directory in ai_developer_growth repo root or package bundle
    source_tools = Path(__file__).resolve().parent.parent.parent.parent / "tools" / "scripts"
    if not source_tools.exists():
        # Fallback if running from installed package
        source_tools = Path(__file__).resolve().parent / "bundled_tools"

    synced_files = []
    if source_tools.exists():
        for src in source_tools.rglob("*"):
            if src.is_file() and "__pycache__" not in str(src):
                rel = src.relative_to(source_tools)
                dest = scripts_dir / rel
                if src.resolve() == dest.resolve():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                synced_files.append(str(rel))

    return {
        "success": True,
        "target": str(target_path),
        "synced_files_count": len(synced_files),
        "synced_files": synced_files,
    }


if __name__ == "__main__":
    res = sync_project_workflows()
    print(f"✅ JCode Workflow Synchronization Result: {res}")
