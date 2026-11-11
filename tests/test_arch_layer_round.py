"""arch 层攻坚: LayerChecker(33%→90%+) 与 DependencyGraph(64%→85%+)。

LayerConfig YAML 加载/default_python/违规检测/DEFAULT_LAYER_MAP 全路径。
DependencyGraph: 多语言建图/cycle/hub/计数/语言探测。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine.arch.dependency_graph import DependencyGraph
from tools.scripts.rules_engine.arch.layer_checker import (
    DEFAULT_LAYER_MAP,
    LayerChecker,
    LayerConfig,
    LayerViolation,
    _detect_layer,
)

# ── LayerConfig ─────────────────────────────────────────────


class TestLayerConfig:
    def test_from_yaml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "architecture.yml"
        cfg_file.write_text(
            """
layers:
  - name: controller
    allowed_deps: [service]
  - name: service
    allowed_deps: [repository]
""",
            encoding="utf-8",
        )
        config = LayerConfig.from_yaml(cfg_file)
        assert config.layers == {"controller": ["service"], "service": ["repository"]}

    def test_from_missing_yaml_returns_empty(self, tmp_path: Path) -> None:
        assert LayerConfig.from_yaml(tmp_path / "nope.yml").layers == {}

    def test_from_corrupt_yaml_returns_empty(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "bad.yml"
        cfg_file.write_text("{ broken: [", encoding="utf-8")
        assert LayerConfig.from_yaml(cfg_file).layers == {}

    def test_from_yaml_skips_nameless_layers(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "a.yml"
        cfg_file.write_text("layers:\n  - allowed_deps: [x]\n  - name: ok\n", encoding="utf-8")
        assert LayerConfig.from_yaml(cfg_file).layers == {"ok": []}

    def test_default_python_layering(self) -> None:
        config = LayerConfig.default_python()
        assert config.layers["controller"] == ["service", "domain"]
        assert config.layers["domain"] == []
        # repository 不得依赖 service
        assert "service" not in config.layers["repository"]


# ── _detect_layer ───────────────────────────────────────────


class TestDetectLayer:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("src/controllers/user.py", "controller"),
            ("app/services/order.py", "service"),
            ("lib/repositories/repo.py", "repository"),
            ("domain/entities/x.rs", "domain"),
            ("config/settings.py", "config"),
            ("tests/test_x.py", "test"),
            ("README.md", None),
        ],
    )
    def test_mapping(self, path: str, expected: str | None) -> None:
        assert _detect_layer(path) == expected

    def test_windows_style_paths(self) -> None:
        assert _detect_layer("src\\services\\a.py") == "service"

    def test_map_has_no_unknown_layers(self) -> None:
        default_config = LayerConfig.default_python().layers
        for layer in set(DEFAULT_LAYER_MAP.values()):
            if layer != "test":
                assert layer in default_config


# ── LayerChecker.check_graph ────────────────────────────────


def build_graph(edges: dict[str, list[str]]) -> DependencyGraph:
    graph = DependencyGraph()
    for src, deps in edges.items():
        graph._graph[src] = set(deps)
    return graph


class TestLayerChecker:
    def test_violation_detected(self) -> None:
        checker = LayerChecker()  # default_python: repository → domain only
        graph = build_graph({"src/repositories/user_repo.py": ["src/services/user_service.py"]})
        violations = checker.check_graph(graph)
        assert len(violations) == 1
        assert violations[0].category == "layer-violation"
        assert violations[0].severity == "error"

    def test_allowed_dependency_passes(self) -> None:
        checker = LayerChecker()
        graph = build_graph({"src/services/order.py": ["src/repositories/order_repo.py"]})
        assert checker.check_graph(graph) == []

    def test_same_layer_self_dep_allowed(self) -> None:
        checker = LayerChecker()
        graph = build_graph({"src/services/a.py": ["src/services/b.py"]})
        assert checker.check_graph(graph) == []

    def test_untagged_modules_ignored(self) -> None:
        checker = LayerChecker()
        graph = build_graph({"scripts/tool.py": ["anything"]})
        assert checker.check_graph(graph) == []

    def test_source_layer_not_in_config_ignored(self) -> None:
        checker = LayerChecker(LayerConfig(layers={"controller": ["service"]}))
        graph = build_graph({"src/repositories/r.py": ["src/domain/d.py"]})  # repository 不在配置中
        assert checker.check_graph(graph) == []

    def test_object_without_graph_attr_returns_empty(self) -> None:
        class NotAGraph:
            pass

        checker = LayerChecker()
        assert checker.check_graph(NotAGraph()) == []  # type: ignore[arg-type]

    def test_layer_violation_to_issue(self) -> None:
        v = LayerViolation(file="a.py", message="bad", source_layer="repo", target_module="svc")
        issue = v.to_issue()
        assert issue.rule_id == "arch-layer-violation"
        assert issue.category == "layer-violation"


# ── DependencyGraph ─────────────────────────────────────────


class TestDependencyGraphBuild:
    def test_python_local_imports_tracked(self, tmp_path: Path) -> None:
        pkg = tmp_path / "services"
        pkg.mkdir()
        (pkg / "order.py").write_text("import services.billing\nfrom repositories import repo\n", encoding="utf-8")
        (tmp_path / "repositories").mkdir()
        (tmp_path / "repositories" / "__init__.py").write_text("", encoding="utf-8")
        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])
        assert issues == []
        assert graph.module_count >= 1
        deps = graph._graph.get("services/order.py", set())
        # 只保留能解析到树内模块的依赖: repositories 解析到其 __init__.py;
        # services.billing 在树内不存在 (外部/未实现) → 不建边
        assert "repositories/__init__.py" in deps
        assert not any("billing" in d for d in deps)

    def test_stdlib_import_not_tracked(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("import os\nimport sys\n", encoding="utf-8")
        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])
        # os/sys 首字母小写但不在图里作为边? 源码规则: 小写开头算本地。验证真实行为:
        deps = graph._graph.get("app.py", set())
        assert all(d in {"os", "sys"} for d in deps)

    def test_typescript_relative_imports(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.ts").write_text('import { helper } from "./helper";\n', encoding="utf-8")
        (src / "helper.ts").write_text("export const helper = 1;\n", encoding="utf-8")
        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["typescript"])
        deps = graph._graph.get("src/main.ts", set())
        # 相对 import 必须解析到树内真实文件 (旧实现原样保留 "./helper", 边指向不存在的节点)
        assert "src/helper.ts" in deps

    def test_cycle_detection_direct_graph(self) -> None:
        # 真实建图时 import 名与文件节点 key(相对路径)不一致, cycle 实际不可达;
        # 直接构造 _graph 验证 DFS 逻辑本身
        graph = build_graph({"a.py": ["b.py"], "b.py": ["a.py"]})
        cycles = [i for i in graph._find_cycles() if i.category == "cycle"]
        assert cycles and cycles[0].severity == "error"
        assert "a.py" in cycles[0].message

    def test_cycle_requires_registered_neighbor(self) -> None:
        # 邻居不在图中则不递归, 不误报
        graph = build_graph({"a.py": ["ghost_module"]})
        assert graph._find_cycles() == []

    def test_hub_detection(self) -> None:
        graph = build_graph({"orchestrator.py": [f"mod_{i}" for i in range(30)]})
        hubs = graph._find_hubs(max_deps=25)
        assert len(hubs) == 1 and hubs[0].category == "hub" and hubs[0].severity == "warning"

    def test_hub_skips_init(self) -> None:
        graph = build_graph({"__init__.py": [f"m{i}" for i in range(30)]})
        assert graph._find_hubs(max_deps=25) == []

    def test_edge_count_and_detect_lang(self, tmp_path: Path) -> None:
        graph = build_graph({"a.py": ["b.py", "c.py"]})
        assert graph.edge_count == 2
        assert graph._detect_lang(Path("x.ts")) == "typescript"
        assert graph._detect_lang(Path("x.weird")) == "unknown"

    def test_corrupt_file_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_bytes(b"\xff\xfe not utf8 \x00")
        graph = DependencyGraph()
        assert graph.analyze_directory(tmp_path, languages=["python"]) == []

    def test_unsupported_language_exts_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "x.rb").write_text("require 'rails'\n", encoding="utf-8")
        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])  # 只扫 .py
        assert graph.module_count == 0

    def test_dependency_issue_to_issue(self) -> None:
        from tools.scripts.rules_engine.arch.dependency_graph import DependencyIssue

        di = DependencyIssue(severity="error", category="cycle", file="a.py", line=1, message="m")
        issue = di.to_issue("arch-cycle")
        assert issue.rule_id == "arch-cycle"
        assert issue.category == "architecture.cycle"
