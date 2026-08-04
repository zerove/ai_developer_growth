"""Architecture analysis engine plugin.

Provides cross-file analysis capabilities:
- Dependency graph construction
- Layer violation detection
- Module health metrics
"""

from __future__ import annotations

from .dependency_graph import DependencyGraph, DependencyIssue
from .layer_checker import LayerChecker, LayerConfig, LayerViolation

__all__ = [
    "DependencyGraph",
    "DependencyIssue",
    "LayerChecker",
    "LayerConfig",
    "LayerViolation",
]
