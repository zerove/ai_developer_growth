"""Tests for tools.scripts.rules_engine.semantic_checker (Phase 33a-1).

覆盖 3 个纯函数 (估时 5 min, 5 min 子任务):
- _check_from_import: from X import Y 中 Y 是否使用
- _check_module_import: import X 中 X.short 是否使用
- ImportGraph.add_edge: 加边 + 反向边同步

详见 ADR-036 Phase 33 子任务分解 + ADR-039 (本次)。
"""

from __future__ import annotations

from tools.scripts.rules_engine.ast_nodes import ImportInfo
from tools.scripts.rules_engine.semantic_checker import (
    ImportGraph,
    SemanticIssue,
    _check_from_import,
    _check_module_import,
)


def make_import(
    module: str = "os",
    names: list[str] | None = None,
    line: int = 1,
    is_from: bool = False,
    level: int = 0,
) -> ImportInfo:
    """ImportInfo 工厂函数 (避免每个测试重复构造)。"""
    return ImportInfo(
        module=module, names=names or [], line=line, is_from=is_from, level=level
    )


class TestCheckFromImport:
    """_check_from_import(): from X import Y 中 Y 是否使用。"""

    def test_unused_name_emits_issue(self) -> None:
        """from X import Y 但 Y 不在 content → 添加 unused-import issue。"""
        imp = make_import(module="os", names=["path"], is_from=True)
        issues: list[SemanticIssue] = []
        content = "import sys\nx = 1\n"  # 无 'path'
        _check_from_import("f.py", imp, content, issues)
        assert len(issues) == 1
        assert issues[0].rule_id == "unused-import"
        assert "path" in issues[0].message
        assert "os" in issues[0].message

    def test_used_name_no_issue(self) -> None:
        """from X import Y 且 Y 在 content 出现多次 → 不发 issue。"""
        imp = make_import(module="os", names=["path"], is_from=True)
        issues: list[SemanticIssue] = []
        # 'path' 出现 2 次 (1 import + 1 usage) → count > 1
        content = "from os import path\npath.join('a', 'b')\n"
        _check_from_import("f.py", imp, content, issues)
        assert issues == []

    def test_empty_names_no_issue(self) -> None:
        """names 为空 (例如 from X import *) → 不发 issue (早期 return)。"""
        imp = make_import(module="os", names=[], is_from=True)
        issues: list[SemanticIssue] = []
        _check_from_import("f.py", imp, "any content", issues)
        assert issues == []

    def test_multiple_names_mixed_usage(self) -> None:
        """from X import A, B, C 中部分使用部分未使用 → 只发未使用的 issue。"""
        imp = make_import(module="os", names=["path", "sys"], is_from=True)
        issues: list[SemanticIssue] = []
        # path 用了, sys 没用
        content = "from os import path, sys\npath.join('a', 'b')\n"
        _check_from_import("f.py", imp, content, issues)
        assert len(issues) == 1
        assert "sys" in issues[0].message


class TestCheckModuleImport:
    """_check_module_import(): import X 中 X.short 是否使用。"""

    def test_unused_module_emits_issue(self) -> None:
        """import X 但 X.short 不在 content → 添加 unused-import issue。"""
        imp = make_import(module="os.path", names=[], is_from=False)
        issues: list[SemanticIssue] = []
        content = "import sys\nx = 1\n"  # 无 'path'
        _check_module_import("f.py", imp, content, issues)
        assert len(issues) == 1
        assert issues[0].rule_id == "unused-import"
        assert "os.path" in issues[0].message

    def test_used_module_no_issue(self) -> None:
        """import X 且 X.short 在 content 出现多次 → 不发 issue。"""
        imp = make_import(module="os.path", names=[], is_from=False)
        issues: list[SemanticIssue] = []
        # 'path' 出现 2 次 (1 import + 1 usage)
        content = "import os.path\npath.join('a', 'b')\n"
        _check_module_import("f.py", imp, content, issues)
        assert issues == []

    def test_empty_module_no_issue(self) -> None:
        """module 为空 (理论上不会发生) → 早期 return 不发 issue。"""
        imp = make_import(module="", names=[], is_from=False)
        issues: list[SemanticIssue] = []
        _check_module_import("f.py", imp, "any content", issues)
        assert issues == []

    def test_nested_module_uses_last_segment(self) -> None:
        """import a.b.c 只检查 'c' (短名)。"""
        imp = make_import(module="a.b.c", names=[], is_from=False)
        issues: list[SemanticIssue] = []
        # 'a' 和 'b' 没用, 只 'c' 用了
        content = "import a.b.c\nc.do_something()\n"
        _check_module_import("f.py", imp, content, issues)
        assert issues == []


class TestImportGraphAddEdge:
    """ImportGraph.add_edge(): 加边 + 反向边 + nodes 同步。"""

    def test_add_edge_basic(self) -> None:
        """A → B 加边后: nodes 含 A + B, edges[A] 含 B, reverse_edges[B] 含 A。"""
        g = ImportGraph()
        g.add_edge("a.py", "b.py")
        assert "a.py" in g.nodes
        assert "b.py" in g.nodes
        assert "b.py" in g.edges["a.py"]
        assert "a.py" in g.reverse_edges["b.py"]

    def test_add_edge_bidirectional(self) -> None:
        """A ↔ B 互为依赖 (实际是 2 条边, 不是 1 条双向)。"""
        g = ImportGraph()
        g.add_edge("a.py", "b.py")
        g.add_edge("b.py", "a.py")
        # 两个方向都有
        assert "b.py" in g.edges["a.py"]
        assert "a.py" in g.edges["b.py"]

    def test_add_edge_duplicate(self) -> None:
        """重复加同一条边 → set 自动去重, 不应异常。"""
        g = ImportGraph()
        g.add_edge("a.py", "b.py")
        g.add_edge("a.py", "b.py")
        assert len(g.edges["a.py"]) == 1
        assert len(g.reverse_edges["b.py"]) == 1

    def test_add_edge_chained(self) -> None:
        """A → B → C 链式依赖。"""
        g = ImportGraph()
        g.add_edge("a.py", "b.py")
        g.add_edge("b.py", "c.py")
        assert g.edges["a.py"] == {"b.py"}
        assert g.edges["b.py"] == {"c.py"}
        # reverse: C ← B ← A
        assert "b.py" in g.reverse_edges["c.py"]
        assert "a.py" in g.reverse_edges["b.py"]
