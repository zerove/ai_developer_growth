"""tree-sitter 解析器的细粒度容错回归测试 (Phase 38).

背景:
    `ast_parser.py` 原先把 12 个语言包写在同一个 try 块里, 缺任何一个
    就 except ImportError -> HAS_TREE_SITTER=False, 于是 parse_file 对
    **所有**语言恒返回 None, AST 语义检查整体静默失效 (fail-open)。
    Phase 38 全量回归实测 62 个测试因此失败。

    修复后按语言逐个导入: 缺 tree_sitter_go 只影响 go。

关键: 这些用例必须在**子进程**里跑, 且必须在导入 ast_parser **之前**
就屏蔽语言包。旧实现是模块加载期就 import 全部语言包, 若在导入之后
才屏蔽, 旧实现同样能正常工作 —— 那样测试就测不出真实缺陷
(变异测试暴露过这一点)。
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 不从 ast_parser 导入映射表: 那样在旧实现下会直接 ImportError,
# 掩盖真实的行为断言。
_LANGUAGE_PACKAGES = [
    "tree_sitter_python",
    "tree_sitter_javascript",
    "tree_sitter_typescript",
    "tree_sitter_rust",
    "tree_sitter_go",
    "tree_sitter_java",
    "tree_sitter_ruby",
    "tree_sitter_cpp",
    "tree_sitter_c_sharp",
    "tree_sitter_kotlin",
    "tree_sitter_php",
    "tree_sitter_swift",
]

_BLOCKER = '''
import sys

BLOCKED = {blocked!r}


class _BlockingFinder:
    """在模块被导入前拦截指定包, 模拟环境里未安装。

    必须实现 PEP 451 的 find_spec: Python 3.12 起导入系统不再回退到
    find_module/load_module, 只写这两个方法的 finder 会被完全忽略,
    屏蔽静默失效 -> 测试变成"永远通过"的假绿灯 (实测 2 项失败)。
    抛 ImportError 而非返回 None, 才能真正模拟"未安装"。
    """

    def find_spec(self, name, path=None, target=None):
        if name in BLOCKED:
            raise ImportError("simulated missing package: " + name)
        return None


sys.meta_path.insert(0, _BlockingFinder())
'''


def _run_probe(blocked: list[str], body: str) -> str:
    """在干净子进程中运行探针, 返回其标准输出。"""
    script = _BLOCKER.format(blocked=blocked) + textwrap.dedent(body)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=180,
    )
    return result.stdout.strip()


class PartialInstallTest(unittest.TestCase):
    """核心回归: 只装部分语言包时, 已装的语言必须仍可解析。"""

    def test_missing_languages_do_not_disable_python(self) -> None:
        """只装 tree_sitter_python 时, python AST 解析必须照常工作。

        这是旧实现会失败的场景: 缺 11 个语言包 -> HAS_TREE_SITTER=False
        -> parse_file 恒返回 None。
        """
        blocked = [p for p in _LANGUAGE_PACKAGES if p != "tree_sitter_python"]
        out = _run_probe(
            blocked,
            """
            from tools.scripts.rules_engine.ast_parser import ASTParser

            parser = ASTParser()
            if "python" not in parser._parsers:
                print("RESULT: NO_PYTHON_PARSER")
            else:
                import tempfile, pathlib
                with tempfile.TemporaryDirectory() as d:
                    f = pathlib.Path(d) / "probe.py"
                    f.write_text("def f():\\n    pass\\n")
                    r = parser.parse_file(f, language="python")
                    print("RESULT:", "OK" if r is not None else "BROKEN")
            """,
        )
        self.assertIn(
            "RESULT: OK",
            out,
            "缺少其他语言包时 python AST 解析失效 —— 全有全无式导入回归了",
        )

    def test_no_tree_sitter_at_all_is_reported(self) -> None:
        """连 tree_sitter 本体都没有时, 必须明确降级而不是假装正常。"""
        out = _run_probe(
            [*_LANGUAGE_PACKAGES, "tree_sitter"],
            """
            from tools.scripts.rules_engine.ast_parser import HAS_TREE_SITTER
            print("RESULT:", "DEGRADED" if not HAS_TREE_SITTER else "CLAIMS_AVAILABLE")
            """,
        )
        self.assertIn("RESULT: DEGRADED", out)

    def test_missing_languages_are_reported_on_stderr(self) -> None:
        """缺失语言要留在日志里, 不能静默 pass。"""
        blocked = [p for p in _LANGUAGE_PACKAGES if p != "tree_sitter_python"]
        script = _BLOCKER.format(blocked=blocked) + textwrap.dedent(
            """
            from tools.scripts.rules_engine.ast_parser import ASTParser
            ASTParser()
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=180,
        )
        self.assertIn(
            "解析器不可用",
            result.stderr,
            "缺失语言未被告警 —— AST 检查会静默不工作",
        )

    def test_every_supported_language_has_a_module_mapping(self) -> None:
        """新增支持语言时不能忘了在映射表中登记。"""
        from tools.scripts.rules_engine import ast_parser as ap

        mapping = getattr(ap, "_LANGUAGE_MODULES", None)
        self.assertIsNotNone(mapping, "_LANGUAGE_MODULES 映射表缺失")
        self.assertEqual(
            set(ap.ASTParser.SUPPORTED_LANGUAGES),
            set(mapping or {}),
            "新增支持语言时忘了在 _LANGUAGE_MODULES 中登记",
        )


class FullyInstalledTest(unittest.TestCase):
    """依赖齐全时的正常路径。"""

    def test_python_parses_real_source(self) -> None:
        from tools.scripts.rules_engine.ast_parser import ASTParser

        parser = ASTParser()
        if "python" not in parser._parsers:
            self.skipTest("tree-sitter 未安装, 跳过正常路径断言")
        result = parser.parse_file(REPO_ROOT / "tools/scripts/rules_engine/ast_parser.py", language="python")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreater(result.total_lines, 0)


if __name__ == "__main__":
    unittest.main()
