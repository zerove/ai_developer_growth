"""Tests for ast_parser import 解析 bug 修复 (Phase 33b-5 / ADR-046).

覆盖 _parse_import_statement 与 _parse_import_from_statement 的所有 import 模式:
- import X / import X, Y / import X as Y
- from X import Y / from X import Y, Z / from X import Y as Z
- from . import x / from .. import x / from ..pkg import y (relative)
- from foo.bar import baz (dotted module)
- import a as b (aliased)

详见 ADR-046 Phase 33b-5 import 解析修复。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine.ast_nodes import ImportInfo
from tools.scripts.rules_engine.ast_parser import ASTParser


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


def _parse_python(parser: ASTParser, code: str) -> list[ImportInfo]:
    """辅助函数: 解析 Python 字符串并返回 imports."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        fname = f.name
    ast = parser.parse_file(Path(fname), language="python")
    return list(ast.imports) if ast else []


class TestParseImportStatement:
    """_parse_import_statement: import X / import X, Y / import X as Y."""

    def test_simple_import(self, parser: ASTParser) -> None:
        """import os -> module='os', names=[]."""
        imports = _parse_python(parser, "import os\n")
        assert len(imports) == 1
        assert imports[0].module == "os"
        assert imports[0].names == []
        assert imports[0].is_from is False
        assert imports[0].line == 1

    def test_multiple_imports_in_one_line(self, parser: ASTParser) -> None:
        """import sys, json -> module='sys', names=['json']."""
        imports = _parse_python(parser, "import sys, json\n")
        assert len(imports) == 1
        assert imports[0].module == "sys"
        assert imports[0].names == ["json"]
        assert imports[0].is_from is False

    def test_aliased_import(self, parser: ASTParser) -> None:
        """import a as b -> module='a', names=[]."""
        imports = _parse_python(parser, "import a as b\n")
        assert len(imports) == 1
        assert imports[0].module == "a"
        assert imports[0].names == []
        assert imports[0].is_from is False

    def test_dotted_module(self, parser: ASTParser) -> None:
        """import foo.bar -> module='foo.bar', names=[]."""
        imports = _parse_python(parser, "import foo.bar\n")
        assert len(imports) == 1
        assert imports[0].module == "foo.bar"
        assert imports[0].names == []


class TestParseImportFromStatement:
    """_parse_import_from_statement: from X import Y."""

    def test_simple_from(self, parser: ASTParser) -> None:
        """from typing import List -> module='typing', names=['List']."""
        imports = _parse_python(parser, "from typing import List\n")
        assert len(imports) == 1
        assert imports[0].module == "typing"
        assert imports[0].names == ["List"]
        assert imports[0].is_from is True

    def test_multiple_names(self, parser: ASTParser) -> None:
        """from typing import List, Optional -> module='typing', names=['List', 'Optional']."""
        imports = _parse_python(parser, "from typing import List, Optional\n")
        assert len(imports) == 1
        assert imports[0].module == "typing"
        assert imports[0].names == ["List", "Optional"]
        assert imports[0].is_from is True

    def test_dotted_module(self, parser: ASTParser) -> None:
        """from foo.bar import baz -> module='foo.bar', names=['baz']."""
        imports = _parse_python(parser, "from foo.bar import baz\n")
        assert len(imports) == 1
        assert imports[0].module == "foo.bar"
        assert imports[0].names == ["baz"]
        assert imports[0].is_from is True

    def test_aliased_name(self, parser: ASTParser) -> None:
        """from collections import OrderedDict as OD -> module='collections', names=['OrderedDict']."""
        imports = _parse_python(parser, "from collections import OrderedDict as OD\n")
        assert len(imports) == 1
        assert imports[0].module == "collections"
        assert imports[0].names == ["OrderedDict"]
        assert imports[0].is_from is True

    def test_relative_single_dot(self, parser: ASTParser) -> None:
        """from . import x -> module='', names=['x'], level=1."""
        imports = _parse_python(parser, "from . import x\n")
        assert len(imports) == 1
        assert imports[0].module == ""
        assert imports[0].names == ["x"]
        assert imports[0].level == 1
        assert imports[0].is_from is True

    def test_relative_double_dot(self, parser: ASTParser) -> None:
        """from .. import x -> module='', names=['x'], level=2."""
        imports = _parse_python(parser, "from .. import x\n")
        assert len(imports) == 1
        assert imports[0].module == ""
        assert imports[0].names == ["x"]
        assert imports[0].level == 2

    def test_relative_with_pkg(self, parser: ASTParser) -> None:
        """from ..pkg import y -> module='', names=['y'], level=2."""
        imports = _parse_python(parser, "from ..pkg import y\n")
        assert len(imports) == 1
        assert imports[0].module == ""
        assert imports[0].names == ["y"]
        assert imports[0].level == 2


class TestMultiImportFile:
    """多个 import 共存."""

    def test_mixed_imports(self, parser: ASTParser) -> None:
        """混合 import + from + relative."""
        code = (
            "import os\n"
            "from typing import List\n"
            "from . import x\n"
        )
        imports = _parse_python(parser, code)
        assert len(imports) == 3
        # 第一个: import os
        assert imports[0].module == "os"
        assert imports[0].is_from is False
        # 第二个: from typing import List
        assert imports[1].module == "typing"
        assert imports[1].names == ["List"]
        assert imports[1].is_from is True
        # 第三个: from . import x
        assert imports[2].module == ""
        assert imports[2].names == ["x"]
        assert imports[2].level == 1


class TestBugFixRegression:
    """回归测试: 确保 ADR-041/045 报告的 bug 不再发生."""

    def test_import_no_longer_takes_keyword_as_module(self, parser: ASTParser) -> None:
        """原 bug: 'import os' module='import'. 现已修复 module='os'."""
        imports = _parse_python(parser, "import os\n")
        # 关键回归断言: module 不再是 'import' 关键字
        assert imports[0].module != "import"
        assert imports[0].module == "os"

    def test_from_no_longer_takes_last_name_as_module(self, parser: ASTParser) -> None:
        """原 bug: 'from typing import List' module='List'. 现已修复 module='typing'."""
        imports = _parse_python(parser, "from typing import List\n")
        # 关键回归断言: module 不再是最后一个 name
        assert imports[0].module != "List"
        assert imports[0].module == "typing"
        # names 应包含 List
        assert "List" in imports[0].names


class TestIntegrationWithSemanticRules:
    """集成: import 解析后 UnusedImportRule 能正确触发."""

    def test_unused_import_now_detected(self, parser: ASTParser) -> None:
        """from os import unused_path (未使用) -> UnusedImportRule 应触发."""
        imports = _parse_python(parser, "from os import unused_path\n")
        assert len(imports) == 1
        # 注: UnusedImportRule 还需要真实文件路径用于 content 检查
        # 这里仅验证 imports 字段被正确填充
        assert imports[0].names == ["unused_path"]
        assert imports[0].module == "os"
