"""架构守卫契约: 依赖图必须解析到真实模块, 循环依赖检测才可能命中。

## 要锁住的缺陷

旧实现把 import 说明符（``services.billing`` / ``./helper``）**原样**写进图,
而图节点是**文件相对路径**（``services/billing.py``）。两者永不相等, 于是:

- 边的终点不是图节点 → 循环依赖检测**永远不可能命中**（静默假绿灯）;
- hub 统计把标准库/第三方也算进去 → 阈值失真。

旧测试甚至把这一点写进了注释（"cycle 实际不可达"）。

## 契约

1. import 必须解析到树内**真实文件**; 解析不到（标准库/第三方）不建边;
2. Python 用 ``ast`` 取 import —— 文档字符串里的示例 import 不产生假边;
3. 自引用（模块导入自己）不成环;
4. 真实循环必须被检出;
5. ``.adg/architecture.yml`` 的 ``cycle_detection`` / ``hub_detection`` 段真正生效
   （启用开关、最大环长、已登记豁免、hub 阈值与排除模式）。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.arch.dependency_graph import (
    ArchitectureSettings,
    DependencyGraph,
)

__all__ = [
    "TestCycleDetection",
    "TestImportResolution",
    "TestSettings",
]


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestImportResolution:
    """import 解析到真实模块。"""

    def test_python_absolute_import_resolves(self, tmp_path: Path) -> None:
        _write(tmp_path / "services" / "billing.py", "VALUE = 1\n")
        _write(tmp_path / "services" / "order.py", "from services.billing import VALUE\n")

        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])

        assert graph._graph["services/order.py"] == {"services/billing.py"}

    def test_python_relative_import_resolves(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "helper.py", "VALUE = 1\n")
        _write(tmp_path / "pkg" / "user.py", "from .helper import VALUE\n")

        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])

        assert graph._graph["pkg/user.py"] == {"pkg/helper.py"}

    def test_stdlib_import_not_in_graph(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.py", "import os\nimport sys\n")

        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])

        assert graph._graph.get("app.py", set()) == set()

    def test_docstring_example_import_is_not_an_edge(self, tmp_path: Path) -> None:
        """文档字符串里的示例 import 不得产生假边（旧实现用正则会误采）。"""
        _write(tmp_path / "real.py", "VALUE = 1\n")
        _write(
            tmp_path / "app.py",
            '"""用法示例:\n\n    from real import VALUE\n"""\n',
        )

        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])

        assert graph._graph.get("app.py", set()) == set()

    def test_self_import_is_not_an_edge(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.py", "from app import VALUE\nVALUE = 1\n")

        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["python"])

        assert graph._graph.get("app.py", set()) == set()

    def test_typescript_relative_import_resolves(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "helper.ts", "export const helper = 1;\n")
        _write(tmp_path / "src" / "main.ts", 'import { helper } from "./helper";\n')

        graph = DependencyGraph()
        graph.analyze_directory(tmp_path, languages=["typescript"])

        assert graph._graph["src/main.ts"] == {"src/helper.ts"}


class TestCycleDetection:
    """真实循环必须被检出。"""

    def test_python_cycle_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "from b import B\n")
        _write(tmp_path / "b.py", "from a import A\n")

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])

        cycles = [i for i in issues if i.category == "cycle"]
        assert cycles, "真实循环依赖必须被检出"
        assert "a.py" in cycles[0].message and "b.py" in cycles[0].message

    def test_typescript_cycle_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.ts", 'import { b } from "./b";\nexport const a = b;\n')
        _write(tmp_path / "b.ts", 'import { a } from "./a";\nexport const b = a;\n')

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["typescript"])

        assert [i for i in issues if i.category == "cycle"]

    def test_no_cycle_without_cycle(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "from b import B\n")
        _write(tmp_path / "b.py", "VALUE = 1\n")

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])

        assert not [i for i in issues if i.category == "cycle"]


class TestSettings:
    """``.adg/architecture.yml`` 的相关段落必须真正生效。"""

    def _write_config(self, tmp_path: Path, body: str) -> None:
        _write(tmp_path / ".adg" / "architecture.yml", body)

    def test_cycle_detection_can_be_disabled(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "from b import B\n")
        _write(tmp_path / "b.py", "from a import A\n")
        self._write_config(tmp_path, "cycle_detection:\n  enabled: false\n")

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])

        assert not [i for i in issues if i.category == "cycle"]

    def test_registered_exemption_suppresses_cycle(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "from b import B\n")
        _write(tmp_path / "b.py", "from a import A\n")
        self._write_config(
            tmp_path,
            "cycle_detection:\n"
            "  enabled: true\n"
            "  exemptions:\n"
            "    - modules: ['a.py', 'b.py']\n"
            "      reason: '已知存量循环'\n",
        )

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])

        assert not [i for i in issues if i.category == "cycle"]

    def test_unrelated_exemption_does_not_suppress(self, tmp_path: Path) -> None:
        """豁免必须"环中每个模块都命中" —— 沾边不豁免。"""
        _write(tmp_path / "a.py", "from b import B\n")
        _write(tmp_path / "b.py", "from a import A\n")
        self._write_config(
            tmp_path,
            "cycle_detection:\n  exemptions:\n    - modules: ['a.py']\n      reason: '只豁免一半'\n",
        )

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])

        assert [i for i in issues if i.category == "cycle"]

    def test_hub_threshold_from_config(self, tmp_path: Path) -> None:
        for i in range(5):
            _write(tmp_path / f"m{i}.py", "VALUE = 1\n")
        _write(tmp_path / "hub.py", "".join(f"import m{i}\n" for i in range(5)))
        self._write_config(tmp_path, "hub_detection:\n  enabled: true\n  threshold: 3\n")

        graph = DependencyGraph()
        issues = graph.analyze_directory(tmp_path, languages=["python"])

        hubs = [i for i in issues if i.category == "hub"]
        assert hubs, "hub 阈值必须取自配置"
        assert hubs[0].file == "hub.py"

    def test_missing_config_uses_defaults(self, tmp_path: Path) -> None:
        settings = ArchitectureSettings.from_yaml(tmp_path / ".adg" / "architecture.yml")

        assert settings.cycle_detection_enabled is True
        assert settings.hub_threshold == 25
        assert settings.cycle_exemptions == []

    def test_broken_config_does_not_disable_checks(self, tmp_path: Path) -> None:
        """配置坏了也不能让检查整体消失 (fail-open 的反面)。"""
        _write(tmp_path / ".adg" / "architecture.yml", "cycle_detection: [oops\n")

        settings = ArchitectureSettings.from_yaml(tmp_path / ".adg" / "architecture.yml")

        assert settings.cycle_detection_enabled is True
        assert settings.hub_detection_enabled is True
