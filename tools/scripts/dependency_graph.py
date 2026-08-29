"""
Dependency Graph Analysis Module

核心功能:
- 传递依赖解析
- 循环依赖检测
- 依赖树可视化
- 依赖冲突检测
- 影响分析
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.scripts.supply_chain import SBOM, Dependency

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """依赖图节点"""

    name: str
    version: str
    ecosystem: str
    license: str | None = None
    is_direct: bool = True
    vulnerabilities: list[str] = field(default_factory=list)  # vulnerability IDs
    incoming: set[str] = field(default_factory=set)  # 依赖此包的包
    outgoing: set[str] = field(default_factory=set)  # 此包依赖的包


@dataclass
class CircularDependency:
    """循环依赖"""

    cycle: list[str]  # 包名列表，形成环
    ecosystems: list[str]
    severity: str = "warning"  # warning, error


@dataclass
class DependencyConflict:
    """依赖冲突"""

    package_name: str
    versions: dict[str, list[str]]  # version -> [requiring_packages]
    severity: str = "warning"


@dataclass
class ImpactAnalysis:
    """影响分析结果"""

    package: str
    version: str
    direct_dependents: list[str]  # 直接依赖此包的包
    transitive_dependents: list[str]  # 传递依赖此包的包
    total_affected: int
    critical_path: list[str]  # 关键路径


class DependencyGraph:
    """依赖图分析器"""

    def __init__(self) -> None:
        self.nodes: dict[str, DependencyNode] = {}
        self.edges: list[tuple[str, str]] = []  # (from, to)
        self.root_package: str | None = None

    def build_from_sbom(self, sbom: SBOM) -> None:
        """从 SBOM 构建依赖图.

        V2.20 P4-9 拆分: 复用 _add_node_if_missing (P4-6 抽出) + _add_sbom_relationships,
        主函数 3 段线性: clear → add nodes → add root → add relationships.
        """
        self.nodes.clear()
        self.edges.clear()

        # 添加所有包作为节点
        for dep in sbom.packages:
            self._add_node_if_missing(dep, dep.is_direct)

        # 添加根节点
        root_key = f"ROOT:{sbom.name}:{sbom.version}"
        self.root_package = root_key
        self.nodes[root_key] = DependencyNode(
            name=sbom.name,
            version=sbom.version,
            ecosystem="root",
            is_direct=True,
        )

        # 解析关系
        self._add_sbom_relationships(sbom.relationships)

    def _add_sbom_relationships(self, relationships: list[dict[str, str]]) -> None:
        """解析 SBOM relationships, 添加 DEPENDS_ON 边.

        Args:
            relationships: SBOM relationships 列表
        """
        for rel in relationships:
            rel_type = rel.get("relationshipType", "")
            if rel_type == "DEPENDS_ON":
                from_id = rel.get("spdxElementId", "")
                to_id = rel.get("relatedSpdxElement", "")
                self._add_edge(from_id, to_id)

    def build_from_dependencies(
        self, deps: list[Dependency], root_name: str = "project", root_version: str = "1.0.0"
    ) -> None:
        """从依赖列表构建图 (用于无 SBOM 关系的情况).

        V2.20 P4-6 拆分: 抽 _add_node_if_missing / _process_transitive_dependencies,
        主函数仅负责 root + 遍历 deps.
        """
        self.nodes.clear()
        self.edges.clear()

        # 添加根节点
        root_key = f"ROOT:{root_name}:{root_version}"
        self.root_package = root_key
        self.nodes[root_key] = DependencyNode(
            name=root_name,
            version=root_version,
            ecosystem="root",
            is_direct=True,
        )

        # 添加所有依赖
        for dep in deps:
            key = self._add_node_if_missing(dep, dep.is_direct)
            # 根节点依赖所有直接依赖
            if dep.is_direct:
                self._add_edge(root_key, key)
            # 处理传递依赖
            self._process_transitive_dependencies(dep, key)

    def _add_node_if_missing(self, dep: Dependency, is_direct: bool) -> str:
        """添加节点 (若不存在), 返回节点 key.

        Args:
            dep: 依赖对象
            is_direct: 是否直接依赖

        Returns:
            节点 key
        """
        key = self._node_key(dep.name, dep.version, dep.ecosystem)
        if key not in self.nodes:
            self.nodes[key] = DependencyNode(
                name=dep.name,
                version=dep.version,
                ecosystem=dep.ecosystem,
                license=dep.license,
                is_direct=is_direct,
                vulnerabilities=[v.id for v in dep.vulnerabilities],
            )
        return key

    def _process_transitive_dependencies(self, dep: Dependency, parent_key: str) -> None:
        """处理 dep 的所有传递依赖, 添加节点 + 边.

        Args:
            dep: 父依赖对象
            parent_key: 父节点 key
        """
        for trans_dep in dep.dependencies:
            trans_key = self._add_node_if_missing(trans_dep, is_direct=False)
            self._add_edge(parent_key, trans_key)

    def _node_key(self, name: str, version: str, ecosystem: str) -> str:
        return f"{ecosystem}:{name}:{version}"

    def _add_edge(self, from_id: str, to_id: str) -> None:
        if from_id in self.nodes and to_id in self.nodes:
            self.nodes[from_id].outgoing.add(to_id)
            self.nodes[to_id].incoming.add(from_id)
            self.edges.append((from_id, to_id))

    def detect_circular_dependencies(self) -> list[CircularDependency]:
        """检测循环依赖 (使用 Tarjan 算法)"""
        index = 0
        stack: list[str] = []
        on_stack: set[str] = set()
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        cycles: list[list[str]] = []

        def strongconnect(node_id: str) -> None:
            nonlocal index
            indices[node_id] = index
            lowlinks[node_id] = index
            index += 1
            stack.append(node_id)
            on_stack.add(node_id)

            for neighbor in self.nodes[node_id].outgoing:
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlinks[node_id] = min(lowlinks[node_id], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node_id] = min(lowlinks[node_id], indices[neighbor])

            if lowlinks[node_id] == indices[node_id]:
                # 找到一个强连通分量
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node_id:
                        break
                if len(scc) > 1:
                    cycles.append(scc)

        for node_id in self.nodes:
            if node_id not in indices:
                strongconnect(node_id)

        # 转换为 CircularDependency 对象
        result = []
        for cycle in cycles:
            ecosystems = list(set(self.nodes[n].ecosystem for n in cycle))
            result.append(
                CircularDependency(
                    cycle=cycle,
                    ecosystems=ecosystems,
                    severity="error" if len(cycle) <= 3 else "warning",
                )
            )

        return result

    def detect_conflicts(self) -> list[DependencyConflict]:
        """检测依赖版本冲突"""
        # 按包名分组
        by_name: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

        for node_id, node in self.nodes.items():
            if node_id.startswith("ROOT:"):
                continue
            by_name[node.name][node.version].append(node_id)

        conflicts = []
        for pkg_name, versions in by_name.items():
            if len(versions) > 1:
                conflicts.append(
                    DependencyConflict(
                        package_name=pkg_name,
                        versions=dict(versions),
                        severity="error" if len(versions) > 2 else "warning",
                    )
                )

        return conflicts

    def get_transitive_dependencies(self, package_key: str) -> set[str]:
        """获取传递依赖 (所有下游依赖)"""
        visited = set()
        stack = [package_key]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self.nodes[current].outgoing:
                if neighbor not in visited:
                    stack.append(neighbor)

        visited.discard(package_key)
        return visited

    def get_transitive_dependents(self, package_key: str) -> set[str]:
        """获取传递依赖者 (所有上游依赖)"""
        visited = set()
        stack = [package_key]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self.nodes[current].incoming:
                if neighbor not in visited:
                    stack.append(neighbor)

        visited.discard(package_key)
        return visited

    def analyze_impact(self, package_name: str, version: str | None = None) -> list[ImpactAnalysis]:
        """分析升级/移除某包的影响"""
        results = []

        for node_id, node in self.nodes.items():
            if node.name == package_name and (version is None or node.version == version):
                direct = list(node.incoming)
                transitive = self.get_transitive_dependents(node_id)

                # 计算关键路径 (从根节点到此包的最短路径)
                critical_path = self._find_critical_path(node_id)

                results.append(
                    ImpactAnalysis(
                        package=package_name,
                        version=node.version,
                        direct_dependents=direct,
                        transitive_dependents=list(transitive),
                        total_affected=len(direct) + len(transitive),
                        critical_path=critical_path,
                    )
                )

        return results

    def _find_critical_path(self, target_id: str) -> list[str]:
        """从根节点找到目标节点的最短路径.

        V2.20 P4-7 拆分: 抽 _bfs_to_target 收口 BFS 核心循环,
        主函数仅负责 root 守卫 + 委托.
        """
        if not self.root_package or self.root_package not in self.nodes:
            return []
        root = self.root_package
        assert root is not None  # narrow type for mypy
        return self._bfs_to_target(root, target_id)

    def _bfs_to_target(self, root: str, target_id: str) -> list[str]:
        """BFS 寻找从 root 到 target 的最短路径.

        Args:
            root: 起始根节点 (调用前应已 non-None 检查)
            target_id: 目标节点 ID

        Returns:
            路径节点列表 (含首尾), 未找到返 []
        """
        from collections import deque

        queue: deque[tuple[str, list[str]]] = deque([(root, [root])])
        visited = {root}

        while queue:
            current, path = queue.popleft()
            if current == target_id:
                return path
            for neighbor in self.nodes[current].outgoing:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    def get_dependency_tree(self, package_key: str | None = None, max_depth: int = -1) -> dict[str, Any]:
        """获取依赖树 (用于可视化)"""
        if package_key is None:
            package_key = self.root_package

        if package_key is None:
            return {}

        def build_tree(node_id: str, depth: int) -> dict[str, Any]:
            if max_depth >= 0 and depth > max_depth:
                return {"name": self.nodes[node_id].name, "truncated": True}

            node = self.nodes[node_id]
            return {
                "key": node_id,
                "name": node.name,
                "version": node.version,
                "ecosystem": node.ecosystem,
                "license": node.license,
                "is_direct": node.is_direct,
                "vulnerabilities": node.vulnerabilities,
                "children": [build_tree(child, depth + 1) for child in sorted(node.outgoing)],
            }

        return build_tree(package_key, 0)

    def export_graphviz(self, output: Path | None = None) -> str:
        """导出 Graphviz DOT 格式"""
        lines = ["digraph dependencies {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box, style=filled];")

        for node_id, node in self.nodes.items():
            color = "lightgreen" if node.is_direct else "lightblue"
            if node.vulnerabilities:
                color = "lightcoral"
            label = f"{node.name}\\n{node.version}\\n({node.ecosystem})"
            lines.append(f'  "{node_id}" [label="{label}", fillcolor="{color}"];')

        for from_id, to_id in self.edges:
            lines.append(f'  "{from_id}" -> "{to_id}";')

        lines.append("}")

        dot_content = "\n".join(lines)

        if output:
            output.write_text(dot_content)

        return dot_content

    def export_mermaid(self, output: Path | None = None) -> str:
        """导出 Mermaid 图表格式"""
        lines = ["graph TD"]

        for node_id, node in self.nodes.items():
            # 简化节点 ID 用于 Mermaid
            short_id = node_id.replace(":", "_").replace(".", "_").replace("-", "_")
            label = f"{node.name}@{node.version}"
            if node.vulnerabilities:
                label += " ⚠️"
            lines.append(f'  {short_id}["{label}"]')

        for from_id, to_id in self.edges:
            short_from = from_id.replace(":", "_").replace(".", "_").replace("-", "_")
            short_to = to_id.replace(":", "_").replace(".", "_").replace("-", "_")
            lines.append(f"  {short_from} --> {short_to}")

        mermaid_content = "\n".join(lines)

        if output:
            output.write_text(mermaid_content)

        return mermaid_content

    def to_json(self) -> str:
        """导出为 JSON"""
        data = {
            "nodes": {
                k: {
                    "name": v.name,
                    "version": v.version,
                    "ecosystem": v.ecosystem,
                    "license": v.license,
                    "is_direct": v.is_direct,
                    "vulnerabilities": v.vulnerabilities,
                    "incoming": list(v.incoming),
                    "outgoing": list(v.outgoing),
                }
                for k, v in self.nodes.items()
            },
            "edges": self.edges,
            "root": self.root_package,
        }
        return json.dumps(data, indent=2)


def analyze_dependency_graph(
    project_root: Path,
    sbom: SBOM | None = None,
) -> DependencyGraph:
    """便捷函数: 分析项目依赖图"""
    graph = DependencyGraph()

    if sbom:
        graph.build_from_sbom(sbom)
    else:
        # 尝试从项目生成 SBOM 再构建
        from tools.scripts.supply_chain import SupplyChainScanner

        scanner = SupplyChainScanner()
        sbom = scanner.generate_sbom(project_root)
        graph.build_from_sbom(sbom)

    return graph
