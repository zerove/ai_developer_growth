"""Conftest for self-correction-loop tests."""
import sys
from pathlib import Path

# Add src to path so tests can import modules directly
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
