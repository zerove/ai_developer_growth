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


class TestRRules(unittest.TestCase):
    """R anti-pattern tests."""

    def test_r_attach(self):
        with tempfile.NamedTemporaryFile(suffix=".r", mode="w", delete=False) as f:
            f.write("attach(mtcars)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "r")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("r-attach", ids)
        finally:
            filepath.unlink()

    def test_r_sapply(self):
        with tempfile.NamedTemporaryFile(suffix=".r", mode="w", delete=False) as f:
            f.write("result <- sapply(1:10, function(x) x^2)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "r")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("r-sapply", ids)
        finally:
            filepath.unlink()

    def test_r_print(self):
        with tempfile.NamedTemporaryFile(suffix=".r", mode="w", delete=False) as f:
            f.write('print("hello")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "r")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("r-print", ids)
        finally:
            filepath.unlink()

    def test_r_class_check(self):
        with tempfile.NamedTemporaryFile(suffix=".r", mode="w", delete=False) as f:
            f.write('if (class(x) == "character") TRUE\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "r")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("r-sapply-class", ids)
        finally:
            filepath.unlink()

    def test_r_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".r", mode="w", delete=False) as f:
            f.write("MyFunction <- function() {}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "r")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_r_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".r", mode="w", delete=False) as f:
            f.write('my_function <- function(x) {\n  message("processing")\n  x * 2\n}\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "r")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestClojureRules(unittest.TestCase):
    """Clojure anti-pattern tests."""

    def test_clj_eval(self):
        with tempfile.NamedTemporaryFile(suffix=".clj", mode="w", delete=False) as f:
            f.write("(eval (read-string code))\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "clojure")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("clj-eval", ids)
        finally:
            filepath.unlink()

    def test_clj_println(self):
        with tempfile.NamedTemporaryFile(suffix=".clj", mode="w", delete=False) as f:
            f.write('(println "hello")\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "clojure")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("clj-print", ids)
        finally:
            filepath.unlink()

    def test_clj_atom(self):
        with tempfile.NamedTemporaryFile(suffix=".clj", mode="w", delete=False) as f:
            f.write("(def counter (atom 0))\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "clojure")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("clj-atom", ids)
        finally:
            filepath.unlink()

    def test_clj_binding(self):
        with tempfile.NamedTemporaryFile(suffix=".clj", mode="w", delete=False) as f:
            f.write("(binding [*print-readably* true] (println x))\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "clojure")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("clj-var", ids)
        finally:
            filepath.unlink()

    def test_clj_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".clj", mode="w", delete=False) as f:
            f.write("(defn MyFunction [] :ok)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "clojure")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_clj_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".clj", mode="w", delete=False) as f:
            f.write("(defn my-fn [x]\n  (let [y (* x 2)]\n    y))\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "clojure")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestHaskellRules(unittest.TestCase):
    """Haskell anti-pattern tests."""

    def test_hs_unsafe_perform_io(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write("x = unsafePerformIO getContents\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("hs-unsafe-perform-io", ids)
        finally:
            filepath.unlink()

    def test_hs_from_just(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write("x = fromJust (lookup key map)\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("hs-from-just", ids)
        finally:
            filepath.unlink()

    def test_hs_head(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write("x = head [1, 2, 3]\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("hs-head", ids)
        finally:
            filepath.unlink()

    def test_hs_read(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write("x = read input :: Int\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("hs-read", ids)
        finally:
            filepath.unlink()

    def test_hs_print(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write('main = putStrLn "hello"\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("hs-print", ids)
        finally:
            filepath.unlink()

    def test_hs_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write("my_function = 42\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_hs_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".hs", mode="w", delete=False) as f:
            f.write("myFunc :: Int -> Int\nmyFunc x = x * 2\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "haskell")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestDartRules(unittest.TestCase):
    """Dart anti-pattern tests."""

    def test_dt_print(self):
        with tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False) as f:
            f.write('print("hello");\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "dart")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("dt-print", ids)
        finally:
            filepath.unlink()

    def test_dt_dynamic(self):
        with tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False) as f:
            f.write("dynamic x = getData();\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "dart")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("dt-dynamic", ids)
        finally:
            filepath.unlink()

    def test_dt_empty_catch(self):
        with tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False) as f:
            f.write("try { await fetchData(); } catch (e) {}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "dart")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("dt-empty-catch", ids)
        finally:
            filepath.unlink()

    def test_dt_set_state(self):
        with tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False) as f:
            f.write("setState(() { _count++; });\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "dart")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("dt-set-state", ids)
        finally:
            filepath.unlink()

    def test_dt_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False) as f:
            f.write("class my_class {\n  void my_method() {}\n}\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "dart")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 2)
        finally:
            filepath.unlink()

    def test_dt_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".dart", mode="w", delete=False) as f:
            f.write(
                'class MyWidget extends StatelessWidget {\n  @override\n  Widget build(BuildContext context) {\n    return Text("hello");\n  }\n}\n'
            )
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "dart")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()


class TestPowerShellRules(unittest.TestCase):
    """PowerShell anti-pattern tests."""

    def test_ps_write_host(self):
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False) as f:
            f.write('Write-Host "hello"\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "powershell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ps-write-host", ids)
        finally:
            filepath.unlink()

    def test_ps_invoke_expression(self):
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False) as f:
            f.write("Invoke-Expression $userInput\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "powershell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ps-invoke-expression", ids)
        finally:
            filepath.unlink()

    def test_ps_empty_catch(self):
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False) as f:
            f.write("try { Do-Work } catch { }\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "powershell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ps-empty-catch", ids)
        finally:
            filepath.unlink()

    def test_ps_alias(self):
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False) as f:
            f.write("iex $code\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "powershell")
            ids = [i.rule_id for i in result.issues]
            self.assertIn("ps-alias", ids)
        finally:
            filepath.unlink()

    def test_ps_naming(self):
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False) as f:
            f.write("function my-function { }\n")
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "powershell")
            issues = [i for i in result.issues if i.category == "naming"]
            self.assertTrue(len(issues) >= 1)
        finally:
            filepath.unlink()

    def test_ps_clean_code(self):
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False) as f:
            f.write('function Invoke-Process {\n    [CmdletBinding()]\n    param()\n    Write-Output "done"\n}\n')
            f.flush()
            filepath = Path(f.name)
        try:
            result = validate_file(filepath, "powershell")
            err_ids = [i.rule_id for i in result.issues if i.severity == "error"]
            self.assertEqual(len(err_ids), 0)
        finally:
            filepath.unlink()
