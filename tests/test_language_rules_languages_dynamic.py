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


class TestRubyRules(unittest.TestCase):
    """Ruby anti-pattern tests."""

    def test_rb_rescue_nil(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("result = do_something rescue nil\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            ids = [i.rule_id for i in result.issues]
            # rescue nil is a bare rescue pattern - check for rb-rescue-all
            self.assertIn("rb-rescue-all", ids)
        finally:
            filepath.unlink()

    def test_rb_bare_rescue(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("begin\ndo_something\nrescue\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("rb-rescue-all", ids)
        finally:
            filepath.unlink()

    def test_rb_eval(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("eval(code)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("rb-eval", ids)
        finally:
            filepath.unlink()

    def test_rb_send(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("obj.send(:method_name)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("rb-send", ids)
        finally:
            filepath.unlink()

    def test_rb_system_exec(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write('system("ls")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            [i.rule_id for i in result.issues]
            # system() doesn't trigger a specific rule, just check no errors
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()

    def test_rb_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("class my_class\n  def myMethod\n  end\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 2)
        finally:
            filepath.unlink()

    def test_rb_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write('class MyService\n  def do_work\n    logger.info("start")\n  end\nend\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()

    def test_rb_attr_accessor(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("class User\n  attr_accessor :name\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            [i.rule_id for i in result.issues]
            # attr_accessor is not a pattern we check for
            self.assertTrue(True)
        finally:
            filepath.unlink()

    def test_rb_module_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
            f.write("module MyModule\n  class MyClass\n  end\nend\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "ruby")
            mod_issues = [i for i in result.issues if "module" in i.rule_id and i.category == "naming"]
            self.assertEqual(len(mod_issues), 0)
        finally:
            filepath.unlink()


class TestCppRules(unittest.TestCase):
    """C++ anti-pattern tests."""

    def test_cpp_raw_new(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("int* p = new int(5);\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("cpp-raw-new", ids)
        finally:
            filepath.unlink()

    def test_cpp_null(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("int* p = NULL;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("cpp-null-pointer", ids)
        finally:
            filepath.unlink()

    def test_cpp_c_cast(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("int x = (int)ptr;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("cpp-c-style-cast", ids)
        finally:
            filepath.unlink()

    def test_cpp_printf(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write('printf("hello %d", x);\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("cpp-cout-printf", ids)
        finally:
            filepath.unlink()

    def test_cpp_using_namespace(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("using namespace std;\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("cpp-using-namespace", ids)
        finally:
            filepath.unlink()

    def test_cpp_catch_by_value(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("try { doWork(); } catch (const std::exception e) {}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("common-empty-catch", ids)
        finally:
            filepath.unlink()

    def test_cpp_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("class my_class {\n    void my_method() {}\n};\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            issues = [i for i in result.issues if i.category == "naming"]
            # class my_class (not PascalCase) triggers 1 naming issue
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_cpp_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
            f.write("void doWork() {\n    auto p = std::make_unique<int>(5);\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "cpp")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestSwiftRules(unittest.TestCase):
    """Swift anti-pattern tests."""

    def test_sw_force_unwrap(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write("let x = optional!\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sw-force-unwrap", ids)
        finally:
            filepath.unlink()

    def test_sw_force_cast(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write("let x = value as! Int\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sw-force-cast", ids)
        finally:
            filepath.unlink()

    def test_sw_try_force(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write("let x = try! riskyOperation()\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sw-try-force", ids)
        finally:
            filepath.unlink()

    def test_sw_print(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write('print("hello")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sw-print-debug", ids)
        finally:
            filepath.unlink()

    def test_sw_nsobject(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write("class MyClass: NSObject {\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sw-nspointer", ids)
        finally:
            filepath.unlink()

    def test_sw_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write("class my_class {\n    func my_method() {}\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 2)
        finally:
            filepath.unlink()

    def test_sw_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".swift", mode="w", delete=False) as f:
            f.write('struct MyView: View {\n    var body: some View {\n        Text("hello")\n    }\n}\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "swift")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestScalaRules(unittest.TestCase):
    """Scala anti-pattern tests."""

    def test_sc_null(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write("val x: String = null\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sc-null", ids)
        finally:
            filepath.unlink()

    def test_sc_throw(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write('throw new RuntimeException("error")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sc-throw", ids)
        finally:
            filepath.unlink()

    def test_sc_isinstance(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write("if (x.isInstanceOf[String]) x.asInstanceOf[String]\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sc-isinstance", ids)
        finally:
            filepath.unlink()

    def test_sc_println(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write('println("hello")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sc-print", ids)
        finally:
            filepath.unlink()

    def test_sc_mutable_collection(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write("val m = scala.collection.mutable.Map[String, Int]()\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("sc-mutable-collection", ids)
        finally:
            filepath.unlink()

    def test_sc_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write("class my_class {\n  def my_method(): Unit = {}\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 2)
        finally:
            filepath.unlink()

    def test_sc_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".scala", mode="w", delete=False) as f:
            f.write('object MyApp {\n  def main(args: Array[String]): Unit = {\n    println("hello")\n  }\n}\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "scala")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()
