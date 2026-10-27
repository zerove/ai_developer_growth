# 拆分自 tests/test_language_rules_languages.py

"""各语言 anti-pattern 规则测试（Java/Kotlin/C#/PHP/Ruby/C++/Swift/Scala/Elixir/Lua/
JavaScript/Zig/R/Clojure/Haskell/Dart/PowerShell）。

从 test_validate_language_rules.py 拆出：这些用例互不依赖共享 fixture，
只用 tempfile + Path 造临时文件，故与核心校验用例分文件维护。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.validate_language_rules import validate_file


class TestElixirRules(unittest.TestCase):
    """Elixir anti-pattern tests."""

    def test_ex_catch_all(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write("def safe do\n  risky()\nrescue _ -> :error\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ex-catch-all", ids)
        finally:
            filepath.unlink()

    def test_ex_io_inspect(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write("IO.inspect(data)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ex-io-inspect", ids)
        finally:
            filepath.unlink()

    def test_ex_process_sleep(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write("Process.sleep(1000)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ex-process-sleep", ids)
        finally:
            filepath.unlink()

    def test_ex_bare_rescue(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write("def safe do\n  risky()\nrescue\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ex-bare-rescue", ids)
        finally:
            filepath.unlink()

    def test_ex_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write("defmodule my_module do\n  def my_function, do: :ok\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_ex_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write(
                'defmodule MyApp.Worker do\n  def process(data) do\n    Logger.info("processing")\n    :ok\n  end\nend\n'
            )
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()

    def test_ex_io_puts(self):
        with tempfile.NamedTemporaryFile(suffix=".ex", mode="w", delete=False) as f:
            f.write('IO.puts("hello")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "elixir")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ex-io-puts", ids)
        finally:
            filepath.unlink()


class TestLuaRules(unittest.TestCase):
    """Lua anti-pattern tests."""

    def test_lua_global(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("myVar = 42\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("lua-global", ids)
        finally:
            filepath.unlink()

    def test_lua_goto(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("goto done\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("lua-goto", ids)
        finally:
            filepath.unlink()

    def test_lua_loadstring(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("loadstring(code)()\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("lua-loadstring", ids)
        finally:
            filepath.unlink()

    def test_lua_print(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write('print("hello")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("lua-print", ids)
        finally:
            filepath.unlink()

    def test_lua_string_concat(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("local s = s .. v\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("lua-string-concat", ids)
        finally:
            filepath.unlink()

    def test_lua_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("function MyModule.MyFunction()\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_lua_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("local M = {}\n\nfunction M.do_work()\n  return true\nend\n\nreturn M\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()

    def test_lua_rawset(self):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write("rawset(t, key, value)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "lua")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("lua-rawset", ids)
        finally:
            filepath.unlink()


class TestJavaScriptRules(unittest.TestCase):
    """JavaScript anti-pattern tests."""

    def test_js_var(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write("var x = 42;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("js-var", ids)
        finally:
            filepath.unlink()

    def test_js_eval(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write("eval(code);\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("js-eval", ids)
        finally:
            filepath.unlink()

    def test_js_inner_html(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write("el.innerHTML = userContent;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("js-inner-html", ids)
        finally:
            filepath.unlink()

    def test_js_empty_catch(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write("try { doWork(); } catch (e) {}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("js-empty-catch", ids)
        finally:
            filepath.unlink()

    def test_js_console(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write('console.log("hello");\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("js-console", ids)
        finally:
            filepath.unlink()

    def test_js_document_write(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write('document.write("<h1>Hello</h1>");\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("js-document-write", ids)
        finally:
            filepath.unlink()

    def test_js_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write("class my_class {\n  my_method() {}\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_js_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write("const myFunc = () => {\n  return 42;\n};\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "javascript")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestZigRules(unittest.TestCase):
    """Zig anti-pattern tests."""

    def test_zig_catch_all(self):
        with tempfile.NamedTemporaryFile(suffix=".zig", mode="w", delete=False) as f:
            f.write("const x = foo() catch _;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "zig")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("zig-catch-all", ids)
        finally:
            filepath.unlink()

    def test_zig_unreachable(self):
        with tempfile.NamedTemporaryFile(suffix=".zig", mode="w", delete=False) as f:
            f.write("unreachable;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "zig")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("zig-unreachable", ids)
        finally:
            filepath.unlink()

    def test_zig_panic(self):
        with tempfile.NamedTemporaryFile(suffix=".zig", mode="w", delete=False) as f:
            f.write('@panic("error");\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "zig")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("zig-panic", ids)
        finally:
            filepath.unlink()

    def test_zig_debug_print(self):
        with tempfile.NamedTemporaryFile(suffix=".zig", mode="w", delete=False) as f:
            f.write('std.debug.print("hello", .{});\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "zig")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("zig-print", ids)
        finally:
            filepath.unlink()

    def test_zig_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".zig", mode="w", delete=False) as f:
            f.write("fn MyFunction() void {}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "zig")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_zig_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".zig", mode="w", delete=False) as f:
            f.write("pub fn do_work() !void {\n    const x = try foo();\n    return x;\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "zig")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()
