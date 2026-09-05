"""端到端契约测试: monster.py (8 import + 深度 binary + 嵌套 class/function).

Phase 33b-8 验证: 迭代化修复后, 单一文件含多种压力源应能完整解析.
"""

import tempfile
from pathlib import Path

from tools.scripts.rules_engine.ast_parser import ASTParser
from tools.scripts.rules_engine.semantic_checker import SemanticChecker


def test_monster_file_end_to_end() -> None:
    """monster.py 端到端: 8 import 模式 + 500 链 binary + 50 层 class + 50 层 function.

    注意: 嵌套 class (class C0: class C1: ...) 在 Python 语义上是 1 个外层 class 包含嵌套类.
    _walk_classes 在最外层 class_definition 处 return, 不递归 children.
    类似地嵌套 function 算 1 个外层 function.
    """
    code_lines = [
        "import os",
        "import sys, json",
        "from typing import List, Optional",
        "from foo.bar import baz",
        "from . import x",
        "from ..pkg import y",
        "import a as b",
        "from collections import OrderedDict as OD",
        "",
        "# 深度 binary 500 链",
        "x = " + " + ".join("1" for _ in range(500)),
        "",
        "# 嵌套 class 50 层 (Python 允许, 视为 1 个外层 class)",
    ]
    for i in range(50):
        code_lines.append(f"{'    ' * i}class C{i}:")
        code_lines.append(f"{'    ' * (i + 1)}x = 1")
    code_lines.append("")
    # 嵌套 function 50 层
    for i in range(50):
        code_lines.append(f"{'    ' * i}def f{i}():")
        code_lines.append(f"{'    ' * (i + 1)}pass")

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "monster.py"
        p.write_text("\n".join(code_lines))

        parser = ASTParser()
        ast = parser.parse_file(p, language="python")
        assert ast is not None
        # 8 import 模式
        assert len(ast.imports) == 8
        # 嵌套 class 算 1 个 (最外层 C0)
        assert len(ast.classes) == 1
        # 嵌套 function 算 1 个 (最外层 f0)
        assert len(ast.functions) == 1
        # 0 错误节点
        assert len(ast.error_nodes) == 0

        # 端到端: semantic_checker 也能处理
        checker = SemanticChecker()
        result = checker.analyze_directory(p.parent)
        assert result.files_analyzed == 1
        # 不爆栈即通过
        assert isinstance(result.issues, list)


def test_multilang_monster_files() -> None:
    """多语言 monster: JS/Rust/Go/Generic 深度 AST 端到端."""
    parser = ASTParser()

    # JS: 深度 chain
    with tempfile.TemporaryDirectory() as td:
        js = Path(td) / "monster.js"
        js.write_text("const x = " + " + ".join("1" for _ in range(500)) + ";")
        ast = parser.parse_file(js, language="javascript")
        assert ast is not None

    # Rust: 深度 chain
    with tempfile.TemporaryDirectory() as td:
        rs = Path(td) / "monster.rs"
        rs.write_text("fn main() { let x = " + " + ".join("1" for _ in range(500)) + "; }")
        ast = parser.parse_file(rs, language="rust")
        assert ast is not None

    # Go: 深度 chain
    with tempfile.TemporaryDirectory() as td:
        go = Path(td) / "monster.go"
        go.write_text("package main\nfunc main() { x := " + " + ".join("1" for _ in range(500)) + " }")
        ast = parser.parse_file(go, language="go")
        assert ast is not None
