"""端到端 total_lines 契约验证 (Phase 33b-10 / ADR-051).

在真实项目代码上验证 ComplexityMetrics.total_lines 真实可信 (不再是 0).
- 工具: tools/scripts/rules_engine/ (56 个真实文件)
- 工具根: tools/scripts/ (192 个真实文件)
"""

from pathlib import Path

from tools.scripts.rules_engine.semantic_checker import SemanticChecker


def test_total_lines_real_rules_engine() -> None:
    """tools/scripts/rules_engine/ 真实代码 total_lines > 0."""
    result = SemanticChecker().analyze_directory(Path("tools/scripts/rules_engine"))
    assert result.files_analyzed > 0
    assert result.metrics.total_lines > 0, f"期望 total_lines > 0, 实际 {result.metrics.total_lines}"
    # 56 个 Python 文件, 每个文件应至少 10 行, 总行数应 >= 500
    assert result.metrics.total_lines >= 500


def test_total_lines_real_tools_scripts() -> None:
    """整个 tools/scripts/ 真实代码 total_lines > 0."""
    result = SemanticChecker().analyze_directory(Path("tools/scripts"))
    assert result.files_analyzed == 192
    assert result.metrics.total_lines > 0
    # 192 文件, 平均 ~150 行/文件, 期望 >= 10000
    assert result.metrics.total_lines >= 10000


def test_total_lines_specific_file() -> None:
    """特定文件 total_lines 等于实际行数."""
    # ast_parser.py 自己的行数
    f = Path("tools/scripts/rules_engine/ast_parser.py")
    expected_lines = len(f.read_text().splitlines())
    assert expected_lines > 1000  # 确保是大文件

    # 构造含已知行数的临时文件
    test_file = Path("tools/scripts/rules_engine/_test_line_count.py")
    test_content = "\n".join(f"line {i}" for i in range(50)) + "\n"
    test_file.write_text(test_content)
    try:
        # 找到 _test_line_count.py
        for ast_result in []:  # analyze_directory 不返回 per-file ast, 用其他方式
            pass
        # 直接 parse_file 验证
        from tools.scripts.rules_engine.ast_parser import ASTParser

        ast = ASTParser().parse_file(test_file, language="python")
        assert ast is not None
        assert ast.total_lines == 50, f"期望 50 行, 实际 {ast.total_lines}"
    finally:
        test_file.unlink()
