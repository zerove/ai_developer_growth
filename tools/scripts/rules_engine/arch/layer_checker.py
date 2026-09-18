"""Layer violation checker — validates architectural layering rules.

Usage:
    from tools.scripts.rules_engine.arch import LayerChecker, LayerConfig

    config = LayerConfig.from_yaml(Path(".adg/architecture.yml"))
    checker = LayerChecker(config)
    violations = checker.check_graph(dependency_graph)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tools.scripts.rules_engine.logger import logger

from ..models import Issue
from .dependency_graph import DependencyGraph, DependencyIssue


@dataclass
class LayerConfig:
    """Layer configuration for architecture validation.

    Example YAML:
        layers:
          - name: controller
            allowed_deps: [service]
          - name: service
            allowed_deps: [repository]
          - name: repository
            allowed_deps: []
    """

    layers: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> LayerConfig:
        """Load layer config from YAML file."""
        try:
            import yaml

            if path.exists():
                data = yaml.safe_load(path.read_text())
                layers = {}
                for layer in data.get("layers", []):
                    name = layer.get("name")
                    deps = layer.get("allowed_deps", [])
                    if name:
                        layers[name] = deps
                return cls(layers=layers)
        except Exception as exc:
            logger.debug("架构配置解析失败，使用默认: %s", exc)
        return cls()

    @classmethod
    def default_python(cls) -> LayerConfig:
        """Default Python Django/FastAPI layering."""
        return cls(
            layers={
                "controller": ["service", "domain"],
                "api": ["service", "domain"],
                "views": ["service", "domain"],
                "service": ["repository", "domain"],
                "repository": ["domain"],
                "domain": [],
                "models": [],
                "config": [],
            }
        )


@dataclass
class LayerViolation:
    """A layer violation issue."""

    severity: str = "error"
    category: str = "layer-violation"
    file: str = ""
    line: int = 1
    message: str = ""
    source_layer: str = ""
    target_module: str = ""

    def to_issue(self) -> Issue:
        return Issue(
            rule_id="arch-layer-violation",
            severity=self.severity,
            category=self.category,
            file=self.file,
            line=self.line,
            message=self.message,
        )


# Directory name → layer name mapping
DEFAULT_LAYER_MAP: dict[str, str] = {
    "controllers": "controller",
    "views": "views",
    "handlers": "controller",
    "api": "api",
    "routes": "api",
    "services": "service",
    "service": "service",
    "repositories": "repository",
    "repository": "repository",
    "models": "domain",
    "domain": "domain",
    "entities": "domain",
    "config": "config",
    "configuration": "config",
    "middleware": "controller",
    "tests": "test",
}


def _detect_layer(filepath: str) -> str | None:
    """Detect which layer a file belongs to based on its path."""
    parts = filepath.replace("\\", "/").split("/")
    for part in parts:
        if part in DEFAULT_LAYER_MAP:
            return DEFAULT_LAYER_MAP[part]
    return None


class LayerChecker:
    """Check for layer violations in a dependency graph."""

    def __init__(self, config: LayerConfig | None = None) -> None:
        self.config = config or LayerConfig.default_python()

    def check_graph(self, graph: DependencyGraph) -> list[DependencyIssue]:
        """Check all edges in the dependency graph for layer violations."""
        violations: list[DependencyIssue] = []

        # Access internal graph data for this check
        try:
            adjacency = graph._graph
        except AttributeError:
            return violations

        for source_module, deps in adjacency.items():
            source_layer = _detect_layer(source_module)
            if not source_layer or source_layer not in self.config.layers:
                continue

            allowed = set(self.config.layers[source_layer])
            for dep in deps:
                dep_layer = _detect_layer(dep)
                if dep_layer and dep_layer not in allowed and dep_layer != source_layer:
                    violations.append(
                        DependencyIssue(
                            severity="error",
                            category="layer-violation",
                            file=source_module,
                            line=1,
                            message=f"Layer violation: '{source_layer}' depends on '{dep_layer}' (allowed: {allowed})",
                            related_files=[dep],
                        )
                    )

        return violations
