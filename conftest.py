"""Root conftest.py - Minimal configuration for root-level tests only.

Each example project runs its own tests independently:
  cd examples/<project> && PYTHONPATH=src python -m pytest tests/

Root tests (tests/) run from the project root:
  python -m pytest tests/
"""
