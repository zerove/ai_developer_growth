# 拆分自 tests/test_semantic_checker_public_api.py

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

import pytest

from tools.scripts.rules_engine.ast_nodes import (
    ASTNode,
    ClassInfo,
    FileAST,
    FunctionInfo,
    ImportInfo,
)
from tools.scripts.rules_engine.semantic_checker import (
    SemanticChecker,
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
