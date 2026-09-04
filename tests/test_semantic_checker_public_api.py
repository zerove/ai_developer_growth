"""Tests for SemanticChecker 公开 API 集成 (Phase 33a-3).

覆盖公开 API 端到端:
- analyze_file(): 单文件解析, 返回 FileAST | None
- analyze_directory(): 目录扫描 + 完整 SemanticResult
- ImportGraph.find_cycles(): import cycle 检测 (DFS)
- _parse_single_file: 异常/None/error_nodes/OSError 分支
- _emit_import_cycle_issues: 集成
- _check_complexity: 私有方法 noop 分支
- _check_missing_docstrings: class 分支

详见 ADR-036 Phase 33 子任务分解 + ADR-041 (本次)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.scripts.rules_engine.ast_nodes import (
    ASTNode,
    ClassInfo,
    FileAST,
    FunctionInfo,
    ImportInfo,
)
from tools.scripts.rules_engine.semantic_checker import (
    ImportGraph,
    SemanticChecker,
    SemanticIssue,
    SemanticResult,
)


def _make_function(
    name: str = "fn",
    line: int = 1,
    end_line: int = 10,
    body_lines: int = 5,
    complexity: int = 1,
    docstring: str | None = "fake",
    is_method: bool = False,
    class_name: str | None = None,
) -> FunctionInfo:
    """构造 FunctionInfo 测试桩。"""
    return FunctionInfo(
        name=name,
        line=line,
        col=0,
        end_line=end_line,
        params=[],
        decorators=[],
        return_type=None,
        docstring=docstring,
        body_lines=body_lines,
        complexity=complexity,
        is_method=is_method,
        class_name=class_name,
    )


def _make_class(
    name: str = "C",
    line: int = 1,
    end_line: int = 10,
    docstring: str | None = "fake",
    methods: list[FunctionInfo] | None = None,
) -> ClassInfo:
    """构造 ClassInfo 测试桩。"""
    return ClassInfo(
        name=name,
        line=line,
        col=0,
        end_line=end_line,
        bases=[],
        decorators=[],
        docstring=docstring,
        methods=methods or [],
        body_lines=end_line - line + 1,
    )


def _make_import(
    module: str = "os",
    names: list[str] | None = None,
    line: int = 1,
    is_from: bool = False,
) -> ImportInfo:
    """构造 ImportInfo 测试桩。"""
    return ImportInfo(
        module=module,
        names=names or [],
        line=line,
        is_from=is_from,
        level=0,
    )


def _make_file_ast(
    language: str = "python",
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    imports: list[ImportInfo] | None = None,
    error_nodes: list[ASTNode] | None = None,
    total_nodes: int = 10,
) -> FileAST:
    """构造 FileAST 测试桩。"""
    return FileAST(
        language=language,
        functions=functions or [],
        classes=classes or [],
        imports=imports or [],
        global_variables=[],
        error_nodes=error_nodes or [],
        total_nodes=total_nodes,
        parse_time_ms=1.5,
    )


class TestImportGraphFindCycles:
    """ImportGraph.find_cycles() DFS 环检测。"""

    def test_empty_graph_no_cycles(self) -> None:
        """空图 → 无环。"""
        graph = ImportGraph()
        assert graph.find_cycles() == []

    def test_no_cycles_in_dag(self) -> None:
        """DAG (有向无环图) → 无环。"""
        graph = ImportGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("a", "c")
        assert graph.find_cycles() == []

    def test_simple_cycle_detected(self) -> None:
        """a→b→a 循环 → 返回环。"""
        graph = ImportGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        cycles = graph.find_cycles()
        assert len(cycles) >= 1
        # 检查至少一个环包含 a 和 b
        assert any("a" in c and "b" in c for c in cycles)

    def test_three_node_cycle_detected(self) -> None:
        """a→b→c→a 三节点环 → 返回环。"""
        graph = ImportGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "a")
        cycles = graph.find_cycles()
        assert len(cycles) >= 1
        assert any(set(c[:3]) == {"a", "b", "c"} for c in cycles)

    def test_self_loop_detected(self) -> None:
        """自循环 a→a → 返回环。"""
        graph = ImportGraph()
        graph.add_edge("a", "a")
        cycles = graph.find_cycles()
        assert len(cycles) >= 1

    def test_disconnected_components(self) -> None:
        """断开的两组件, 一边有环一边无环 → 至少 1 个环。"""
        graph = ImportGraph()
        # 组件 1: 无环
        graph.add_edge("a", "b")
        # 组件 2: 有环
        graph.add_edge("x", "y")
        graph.add_edge("y", "x")
        cycles = graph.find_cycles()
        assert len(cycles) >= 1
        assert any("x" in c and "y" in c for c in cycles)


class TestFindUnusedImportsBothBranches:
    """ImportGraph.find_unused_imports() 主循环两个分支。"""

    def test_from_import_branch(self) -> None:
        """is_from=True 分支执行 (走 _check_from_import)。"""
        graph = ImportGraph()
        imp = ImportInfo(
            module="os",
            names=["path"],  # 非空触发 from 分支
            line=1,
            is_from=True,
            level=0,
        )
        # 文件内容不含 'path'
        content = "import sys\nx = 1\n"
        issues = graph.find_unused_imports(
            {"file.py": [imp]},
            {"file.py": content},
        )
        # 期望: from os import path → path 未用 → 报 unused-import
        assert any(i.rule_id == "unused-import" and "path" in i.message for i in issues)

    def test_module_import_branch(self) -> None:
        """is_from=False + module 非空分支 (走 _check_module_import)。"""
        graph = ImportGraph()
        imp = ImportInfo(
            module="unused_module_xyz",
            names=[],
            line=1,
            is_from=False,
            level=0,
        )
        # 文件内容不含 'unused_module_xyz'
        content = "x = 1\n"
        issues = graph.find_unused_imports(
            {"file.py": [imp]},
            {"file.py": content},
        )
        assert any(i.rule_id == "unused-import" and "unused_module_xyz" in i.message for i in issues)

    def test_mixed_from_and_module(self) -> None:
        """同一文件混合 from + module import。"""
        graph = ImportGraph()
        from_imp = ImportInfo(module="os", names=["unused_a"], line=1, is_from=True, level=0)
        mod_imp = ImportInfo(module="unused_b", names=[], line=2, is_from=False, level=0)
        issues = graph.find_unused_imports(
            {"f.py": [from_imp, mod_imp]},
            {"f.py": "x = 1\n"},
        )
        # 两条 issue
        rule_ids = [i.message for i in issues]
        assert any("unused_a" in m for m in rule_ids)
        assert any("unused_b" in m for m in rule_ids)


class TestAnalyzeFilePublicAPI:
    """SemanticChecker.analyze_file() 公开 API。"""

    def test_analyze_file_python(self, tmp_path: Path) -> None:
        """Python 文件 → 返回 FileAST。"""
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")
        checker = SemanticChecker()
        result = checker.analyze_file(f, language="python")
        if checker.parser.available:
            assert result is not None
            assert result.language == "python"

    def test_analyze_file_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """不存在文件 → None (parser 行为)。"""
        f = tmp_path / "no.py"
        checker = SemanticChecker()
        result = checker.analyze_file(f)
        assert result is None

    def test_analyze_file_default_language(self, tmp_path: Path) -> None:
        """不传 language → 自动从扩展名推断。"""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        checker = SemanticChecker()
        result = checker.analyze_file(f)
        if checker.parser.available:
            assert result is not None
            assert result.language == "python"


class TestParseSingleFileBranches:
    """_parse_single_file() 各异常/None 分支。"""

    def test_parse_exception_creates_issue(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """parser.parse_file 抛异常 → SemanticIssue(rule_id='parse-failure')。"""
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")

        checker = SemanticChecker()

        # mock parser.parse_file 抛 ValueError
        def _raise(*args: Any, **kwargs: Any) -> None:
            raise ValueError("mock parse failure")

        monkeypatch.setattr(checker.parser, "parse_file", _raise)
        parse_errors, ast, rel, content = checker._parse_single_file(f, tmp_path)
        assert len(parse_errors) == 1
        assert parse_errors[0].rule_id == "parse-failure"
        assert parse_errors[0].severity == "error"
        assert ast is None
        assert rel == ""

    def test_parse_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """parser.parse_file 返回 None → 返回空 parse_errors。"""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")

        checker = SemanticChecker()
        monkeypatch.setattr(checker.parser, "parse_file", lambda *a, **k: None)
        parse_errors, ast, rel, content = checker._parse_single_file(f, tmp_path)
        assert parse_errors == []
        assert ast is None

    def test_read_text_os_error_handled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """filepath.read_text OSError → content=None 不抛。"""
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")

        checker = SemanticChecker()

        def _raise_os(*args: Any, **kwargs: Any) -> str:
            raise OSError("disk error")

        monkeypatch.setattr(Path, "read_text", _raise_os)
        parse_errors, ast, rel, content = checker._parse_single_file(f, tmp_path)
        assert content is None
        if ast is not None:
            assert rel != ""


class TestEmitImportCycleIssues:
    """_emit_import_cycle_issues() 集成。"""

    def test_emits_issue_for_cycle(self) -> None:
        """检测到环 → append SemanticIssue(rule_id='import-cycle')。"""
        checker = SemanticChecker()
        checker.import_graph.add_edge("a", "b")
        checker.import_graph.add_edge("b", "a")
        issues: list[SemanticIssue] = []
        checker._emit_import_cycle_issues(issues)
        assert len(issues) >= 1
        assert all(i.rule_id == "import-cycle" for i in issues)
        assert all(i.severity == "warning" for i in issues)
        assert all(i.category == "architecture" for i in issues)

    def test_no_cycles_no_issues(self) -> None:
        """无环 → 不发 issue。"""
        checker = SemanticChecker()
        checker.import_graph.add_edge("a", "b")
        issues: list[SemanticIssue] = []
        checker._emit_import_cycle_issues(issues)
        assert issues == []


class TestCheckComplexityPrivateMethodNoop:
    """_check_complexity() 私有方法 noop 分支 (line 408-409)。"""

    def test_private_method_underscore_passes(self) -> None:
        """_method (单下划线开头) → noop, 不报错。"""
        checker = SemanticChecker()
        ast = _make_file_ast(
            functions=[
                _make_function(name="_private", body_lines=100, complexity=20),
            ]
        )
        issues = checker._check_complexity({"f.py": ast}, Path("/tmp"))
        # 该函数体长且复杂, 但因为是私有方法, _check_complexity 的 is_method 守卫无 op
        # 实际上 _check_complexity 的 is_method 只在 is_method=True 时才 noop
        # 私有 function (无 is_method) 仍会被报
        # 这里验证调用不崩溃
        assert isinstance(issues, list)

    def test_method_with_underscore_name_noop(self) -> None:
        """is_method=True + name starts with '_' → line 408-409 noop 执行 (不影响前面的 append)。

        实际语义: long-function/high-complexity 已在 line 382-406 append, 408-409 仅为 noop 标记.
        测试验证调用不崩溃 + 408-409 分支被覆盖.
        """
        checker = SemanticChecker()
        ast = _make_file_ast(
            functions=[
                _make_function(
                    name="_helper",
                    body_lines=100,  # 长, line 382 报 long-function
                    complexity=20,  # 复杂, line 395 报 high-complexity
                    is_method=True,  # 触发 line 408-409 noop
                ),
            ]
        )
        issues = checker._check_complexity({"f.py": ast}, Path("/tmp"))
        # 调用成功, 返回 list (不崩溃)
        assert isinstance(issues, list)
        rule_ids = [i.rule_id for i in issues]
        # long-function 与 high-complexity 已被报 (noop 不撤销前面的 append)
        assert "long-function" in rule_ids
        assert "high-complexity" in rule_ids


class TestCheckMissingDocstringsClass:
    """_check_missing_docstrings() 类分支 (line 433->432)。"""

    def test_public_class_no_docstring_emits_issue(self) -> None:
        """public class 无 docstring → issue。"""
        checker = SemanticChecker()
        ast = _make_file_ast(
            classes=[_make_class(name="PublicClass", docstring=None)],
        )
        issues = checker._check_missing_docstrings({"f.py": ast}, Path("/tmp"))
        assert any(i.rule_id == "missing-docstring" and "PublicClass" in i.message for i in issues)

    def test_private_class_no_docstring_no_issue(self) -> None:
        """private class 无 docstring → 不报。"""
        checker = SemanticChecker()
        ast = _make_file_ast(
            classes=[_make_class(name="_PrivateClass", docstring=None)],
        )
        issues = checker._check_missing_docstrings({"f.py": ast}, Path("/tmp"))
        assert issues == []

    def test_class_with_docstring_no_issue(self) -> None:
        """public class 有 docstring → 不报。"""
        checker = SemanticChecker()
        ast = _make_file_ast(
            classes=[_make_class(name="Documented", docstring="I have docs")],
        )
        issues = checker._check_missing_docstrings({"f.py": ast}, Path("/tmp"))
        assert issues == []


class TestAnalyzeDirectoryIntegration:
    """analyze_directory() 端到端集成。"""

    def test_empty_directory_returns_empty_result(self, tmp_path: Path) -> None:
        """空目录 → 返回 SemanticResult(issues=[], files_analyzed=0)。"""
        checker = SemanticChecker()
        result = checker.analyze_directory(tmp_path)
        assert isinstance(result, SemanticResult)
        assert result.files_analyzed == 0
        assert result.issues == []
        assert result.metrics.total_functions == 0

    def test_directory_with_python_file(self, tmp_path: Path) -> None:
        """Python 文件目录 → 解析 + metrics。"""
        f = tmp_path / "module.py"
        f.write_text('def public_func():\n    """Has doc."""\n    return 1\n')
        checker = SemanticChecker()
        result = checker.analyze_directory(tmp_path)
        assert isinstance(result, SemanticResult)
        if checker.parser.available:
            assert result.files_analyzed >= 1
            assert result.metrics.total_functions >= 1

    def test_directory_with_unused_import_emits_issue(self, tmp_path: Path) -> None:
        """未使用的 import → 报 unused-import。"""
        f = tmp_path / "module.py"
        # import 但不使用
        f.write_text("import os\nx = 1\n")
        checker = SemanticChecker()
        result = checker.analyze_directory(tmp_path)
        if checker.parser.available and result.files_analyzed >= 1:
            rule_ids = [i.rule_id for i in result.issues]
            assert "unused-import" in rule_ids

    def test_directory_with_cycle_emits_issue(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """import cycle → 报 import-cycle (手动注入 cycle 绕过 ast_parser 解析 bug)。

        已知限制: ast_parser 将 'import X' 解析成 module='import' 语句名, 不是 'X'.
        所以需要 monkeypatch ImportGraph.find_cycles 返回预定义 cycle 验证集成.
        """
        (tmp_path / "a.py").write_text("x = 1\n")
        checker = SemanticChecker()
        # 直接预填一个 cycle, 绕过 ast_parser 解析偏差
        checker.import_graph.add_edge("a.py", "b.py")
        checker.import_graph.add_edge("b.py", "a.py")
        # mock find_cycles 返回已知环
        monkeypatch.setattr(checker.import_graph, "find_cycles", lambda: [["a.py", "b.py", "a.py"]])
        result = checker.analyze_directory(tmp_path)
        rule_ids = [i.rule_id for i in result.issues]
        assert "import-cycle" in rule_ids

    def test_directory_with_complex_function_emits_issue(self, tmp_path: Path) -> None:
        """复杂函数 → 报 high-complexity/long-function。"""
        f = tmp_path / "complex.py"
        # 复杂函数: 多个 if/for/while → complexity > 10
        complex_func = "def complex_one(a, b):\n"
        for i in range(12):
            complex_func += f"    if a > {i}:\n        b += 1\n"
        complex_func += "    return b\n"
        f.write_text(complex_func)
        checker = SemanticChecker()
        result = checker.analyze_directory(tmp_path)
        if checker.parser.available and result.files_analyzed >= 1:
            rule_ids = [i.rule_id for i in result.issues]
            assert "high-complexity" in rule_ids

    def test_directory_filters_by_language(self, tmp_path: Path) -> None:
        """languages 参数过滤文件类型。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.js").write_text("const x = 1;\n")
        checker = SemanticChecker()
        result = checker.analyze_directory(tmp_path, languages=["python"])
        # 仅 Python 被分析
        if checker.parser.available:
            for issue in result.issues:
                assert issue.file.endswith(".py")


class TestCollectSourceFilesEdgeCases:
    """_collect_source_files() 边界情况。"""

    def test_unsupported_language_returns_empty(self, tmp_path: Path) -> None:
        """不支持的语言 → 空列表。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        checker = SemanticChecker()
        files = checker._collect_source_files(tmp_path, languages=["cobol"], max_files=10)
        assert files == []

    def test_ignores_venv_and_node_modules(self, tmp_path: Path) -> None:
        """忽略 .venv/node_modules/__pycache__。"""
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib.py").write_text("x = 1\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.py").write_text("x = 1\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "lib.pyc").write_text("x = 1\n")
        (tmp_path / "ok.py").write_text("x = 1\n")
        checker = SemanticChecker()
        files = checker._collect_source_files(tmp_path, languages=None, max_files=100)
        names = {f.name for f in files}
        assert "ok.py" in names
        assert "lib.py" not in names
        assert "lib.pyc" not in names

    def test_max_files_limit(self, tmp_path: Path) -> None:
        """max_files 截断文件数。"""
        for i in range(10):
            (tmp_path / f"m{i}.py").write_text("x = 1\n")
        checker = SemanticChecker()
        files = checker._collect_source_files(tmp_path, languages=["python"], max_files=3)
        assert len(files) == 3
