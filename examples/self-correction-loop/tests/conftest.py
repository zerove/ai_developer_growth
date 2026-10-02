"""Conftest for self-correction-loop tests."""

import sys
from pathlib import Path

# Add src to path so tests can import modules directly
pkg_root = Path(__file__).parent.parent
src_dir = pkg_root / "src"
for _p in (src_dir, pkg_root):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
