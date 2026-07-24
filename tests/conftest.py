"""Shared test configuration for ai_developer_growth tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Add tools/scripts to sys.path so that rules/__init__.py's
# `from rules.loader import ...` style imports work correctly.
_scripts_dir = str(Path(__file__).resolve().parent.parent / "tools" / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
