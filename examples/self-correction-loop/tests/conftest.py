"""Pytest configuration for self-correction-loop tests."""
import sys
from pathlib import Path

# Add the src directory to sys.path so that 'src.xxx' imports work
ROOT = Path(__file__).parent.parent
SRC_DIR = Path(__file__).parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
