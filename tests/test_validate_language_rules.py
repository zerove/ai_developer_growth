"""validate_language_rules 核心校验用例。

覆盖 Issue/ValidationResult/规则加载/anti-pattern/命名/阈值/嵌套/AST/
圈复杂度/语言检测/文件与目录校验/JSON 输出。

各语言 anti-pattern 规则用例见 test_language_rules_languages.py。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.scripts.validate_language_rules import (
    Issue,
    ValidationResult,
    _calc_cyclomatic_complexity,
    _extract_function_lines,
    _max_nesting_depth,
    _max_python_indent_depth,
    check_anti_patterns,
    check_naming_conventions,
    check_python_ast,
    check_thresholds,
    detect_language_from_file,
    load_rules,
    validate_directory,
    validate_file,
)

# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def python_rules():
    """Load Python rules."""
    return load_rules("python")


@pytest.fixture
def ts_rules():
    """Load TypeScript rules."""
    return load_rules("typescript")


@pytest.fixture
def rust_rules():
    """Load Rust rules."""
    return load_rules("rust")


@pytest.fixture
def go_rules():
    """Load Go rules."""
    return load_rules("go")


# ──────────────────────────────────────────────────────────
# Issue and ValidationResult tests
# ──────────────────────────────────────────────────────────


class TestIssue:
    def test_create_issue(self):
        issue = Issue(
            rule_id="py-test",
            severity="error",
            category="test",
            file="test.py",
            line=10,
            message="Test issue",
            fix_hint="Fix it",
            column=5,
        )
        assert issue.rule_id == "py-test"
        assert issue.severity == "error"
        assert issue.line == 10
        assert issue.column == 5

    def test_issue_to_dict(self):
        issue = Issue(
            rule_id="py-test",
            severity="warning",
            category="test",
            file="test.py",
            line=1,
            message="msg",
        )
        d = issue.to_dict()
        assert d["rule_id"] == "py-test"
        assert d["severity"] == "warning"
        assert d["file"] == "test.py"


class TestValidationResult:
    def test_passed_when_no_errors(self):
        r = ValidationResult(file="f.py", language="python")
        r.issues.append(Issue("x", "warning", "c", "f.py", 1, "m"))
        assert r.passed is True

    def test_failed_when_errors(self):
        r = ValidationResult(file="f.py", language="python")
        r.issues.append(Issue("x", "error", "c", "f.py", 1, "m"))
        assert r.passed is False

    def test_counts(self):
        r = ValidationResult(file="f.py", language="python")
        r.issues.extend(
            [
                Issue("a", "error", "c", "f.py", 1, "m"),
                Issue("b", "warning", "c", "f.py", 2, "m"),
                Issue("c", "info", "c", "f.py", 3, "m"),
                Issue("d", "error", "c", "f.py", 4, "m"),
            ]
        )
        assert r.error_count == 2
        assert r.warning_count == 1
        assert r.info_count == 1

    def test_to_dict(self):
        r = ValidationResult(file="f.py", language="python")
        r.lines_checked = 100
        d = r.to_dict()
        assert d["file"] == "f.py"
        assert d["lines_checked"] == 100
        assert d["passed"] is True


# ──────────────────────────────────────────────────────────
# Rule loading tests
# ──────────────────────────────────────────────────────────


class TestRuleLoading:
    def test_load_python_rules(self, python_rules):
        assert python_rules.get("language") == "python"
        assert "anti_patterns" in python_rules
        assert len(python_rules["anti_patterns"]) > 10

    def test_load_ts_rules(self, ts_rules):
        assert ts_rules.get("language") == "typescript"
        assert len(ts_rules["anti_patterns"]) >= 10

    def test_load_rust_rules(self, rust_rules):
        assert rust_rules.get("language") == "rust"
        assert "rs-unwrap" in [r["id"] for r in rust_rules["anti_patterns"]]

    def test_load_go_rules(self, go_rules):
        assert go_rules.get("language") == "go"
        assert "go-panic-in-library" in [r["id"] for r in go_rules["anti_patterns"]]

    def test_rules_have_required_fields(self, python_rules):
        for rule in python_rules["anti_patterns"]:
            assert "id" in rule
            assert "severity" in rule
            assert "pattern" in rule
            assert "message" in rule
            assert rule["severity"] in ("error", "warning", "info")

    def test_rules_have_thresholds(self, python_rules):
        t = python_rules.get("thresholds", {})
        assert "max_line_length" in t
        assert "max_file_length" in t
        assert "max_function_length" in t


# ──────────────────────────────────────────────────────────
# Anti-pattern detection tests
# ──────────────────────────────────────────────────────────


class TestAntiPatternDetection:
    def test_bare_except_detected(self, python_rules):
        lines = ["try:", "    x = 1", "except:", "    pass"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-bare-except" in ids

    def test_bare_except_pass_detected(self, python_rules):
        lines = ["except Exception: pass"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-bare-except-pass" in ids

    def test_eval_detected(self, python_rules):
        lines = ["result = eval(user_input)"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-eval-exec" in ids

    def test_exec_detected(self, python_rules):
        lines = ["exec(code_string)"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-eval-exec" in ids

    def test_hardcoded_secret_detected(self, python_rules):
        lines = ['password = "my_secret_123"']
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-hardcoded-secret" in ids

    def test_wildcard_import_detected(self, python_rules):
        lines = ["from os import *"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-star-import" in ids

    def test_global_statement_detected(self, python_rules):
        lines = ["def f():", "    global x"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-global-statement" in ids

    def test_mutable_default_detected(self, python_rules):
        lines = ["def f(items=[]):", "    pass"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-mutable-default" in ids

    def test_shell_true_detected(self, python_rules):
        lines = ["subprocess.run(cmd, shell=True)"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-shell-true" in ids

    def test_sql_string_format_detected(self, python_rules):
        lines = ['cursor.execute(f"SELECT * FROM users WHERE id = {uid}")']
        issues = check_anti_patterns(lines, python_rules, "test.py")
        ids = [i.rule_id for i in issues]
        assert "py-sql-string-format" in ids

    def test_clean_code_no_issues(self, python_rules):
        lines = [
            "import logging",
            "from pathlib import Path",
            "",
            "logger = logging.getLogger(__name__)",
            "",
            "def process_data(items: list[int]) -> list[int]:",
            '    """Process data."""',
            "    return [x * 2 for x in items]",
        ]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        # Only check for errors/warnings; info-level suggestions are allowed
        serious = [i for i in issues if i.severity in ("error", "warning")]
        assert len(serious) == 0

    def test_skip_comments(self, python_rules):
        lines = ["# except: pass", "# eval(x)"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        assert len(issues) == 0

    def test_ts_any_type_detected(self, ts_rules):
        lines = ["function f(data: any): any {"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-any-type" in ids

    def test_ts_as_any_detected(self, ts_rules):
        lines = ["const x = value as any;"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-any-type" in ids

    def test_ts_empty_catch_detected(self, ts_rules):
        lines = ["} catch (error) {}"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-empty-catch" in ids

    def test_ts_innerhtml_detected(self, ts_rules):
        lines = ["element.innerHTML = userInput;"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-inner-html" in ids

    def test_ts_var_detected(self, ts_rules):
        lines = ["var count = 0;"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-var-declaration" in ids

    def test_ts_console_log_detected(self, ts_rules):
        lines = ["console.log('debug');"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-console-log" in ids

    def test_ts_require_detected(self, ts_rules):
        lines = ["const fs = require('fs');"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-require-import" in ids

    def test_ts_skip_test_detected(self, ts_rules):
        lines = ["it.skip('should work', () => {});"]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-skip-test" in ids

    def test_ts_empty_test_detected(self, ts_rules):
        lines = ["it('should pass') {}", ""]
        issues = check_anti_patterns(lines, ts_rules, "test.ts")
        ids = [i.rule_id for i in issues]
        assert "ts-no-op-test" in ids

    def test_rust_unwrap_detected(self, rust_rules):
        lines = ["let x = value.unwrap();"]
        issues = check_anti_patterns(lines, rust_rules, "test.rs")
        ids = [i.rule_id for i in issues]
        assert "rs-unwrap" in ids

    def test_rust_expect_detected(self, rust_rules):
        lines = ['let x = value.expect("failed");']
        issues = check_anti_patterns(lines, rust_rules, "test.rs")
        ids = [i.rule_id for i in issues]
        assert "rs-expect" in ids

    def test_rust_panic_detected(self, rust_rules):
        lines = ['panic!("something went wrong");']
        issues = check_anti_patterns(lines, rust_rules, "test.rs")
        ids = [i.rule_id for i in issues]
        assert "rs-panic" in ids

    def test_rust_unsafe_detected(self, rust_rules):
        lines = ["unsafe { ptr.read() }"]
        issues = check_anti_patterns(lines, rust_rules, "test.rs")
        ids = [i.rule_id for i in issues]
        assert "rs-unsafe" in ids

    def test_rust_dbg_detected(self, rust_rules):
        lines = ["dbg!(&value);"]
        issues = check_anti_patterns(lines, rust_rules, "test.rs")
        ids = [i.rule_id for i in issues]
        assert "rs-print" in ids

    def test_go_panic_detected(self, go_rules):
        lines = ['panic("not implemented")']
        issues = check_anti_patterns(lines, go_rules, "test.go")
        ids = [i.rule_id for i in issues]
        assert "go-panic-in-library" in ids

    def test_go_underscore_error_detected(self, go_rules):
        lines = ["result, _ := doSomething()"]
        issues = check_anti_patterns(lines, go_rules, "test.go")
        ids = [i.rule_id for i in issues]
        assert "go-underscore-error" in ids

    def test_go_init_func_detected(self, go_rules):
        lines = ["func init() {"]
        issues = check_anti_patterns(lines, go_rules, "test.go")
        ids = [i.rule_id for i in issues]
        assert "go-init-func" in ids

    def test_go_fmt_print_detected(self, go_rules):
        lines = ["fmt.Println(result)"]
        issues = check_anti_patterns(lines, go_rules, "test.go")
        ids = [i.rule_id for i in issues]
        assert "go-fmt-print" in ids

    def test_go_tls_skip_detected(self, go_rules):
        lines = ["InsecureSkipVerify: true"]
        issues = check_anti_patterns(lines, go_rules, "test.go")
        ids = [i.rule_id for i in issues]
        assert "go-http-tls-skip" in ids


# ──────────────────────────────────────────────────────────
# Naming convention tests
# ──────────────────────────────────────────────────────────


class TestNamingConventions:
    def test_python_function_snake_case(self, python_rules):
        lines = ["def my_function():"]
        issues = check_naming_conventions(lines, python_rules, "test.py")
        snake_issues = [i for i in issues if "naming" in i.rule_id]
        assert len(snake_issues) == 0

    def test_python_function_bad_name(self, python_rules):
        lines = ["def MyFunction():"]
        issues = check_naming_conventions(lines, python_rules, "test.py")
        snake_issues = [i for i in issues if "naming-function" in i.rule_id]
        assert len(snake_issues) == 1

    def test_python_class_pascal_case(self, python_rules):
        lines = ["class MyClass:"]
        issues = check_naming_conventions(lines, python_rules, "test.py")
        class_issues = [i for i in issues if "naming-class" in i.rule_id]
        assert len(class_issues) == 0

    def test_python_class_bad_name(self, python_rules):
        lines = ["class my_class:"]
        issues = check_naming_conventions(lines, python_rules, "test.py")
        class_issues = [i for i in issues if "naming-class" in i.rule_id]
        assert len(class_issues) == 1

    def test_python_constant_upper(self, python_rules):
        lines = ["MAX_SIZE = 100"]
        issues = check_naming_conventions(lines, python_rules, "test.py")
        const_issues = [i for i in issues if "naming-constant" in i.rule_id]
        assert len(const_issues) == 0

    def test_rust_function_snake_case(self, rust_rules):
        lines = ["pub fn my_function() {"]
        issues = check_naming_conventions(lines, rust_rules, "test.rs")
        fn_issues = [i for i in issues if "naming-function" in i.rule_id]
        assert len(fn_issues) == 0

    def test_rust_struct_pascal_case(self, rust_rules):
        lines = ["pub struct MyStruct {"]
        issues = check_naming_conventions(lines, rust_rules, "test.rs")
        struct_issues = [i for i in issues if "naming-struct" in i.rule_id]
        assert len(struct_issues) == 0

    def test_rust_struct_bad_name(self, rust_rules):
        lines = ["pub struct my_struct {"]
        issues = check_naming_conventions(lines, rust_rules, "test.rs")
        struct_issues = [i for i in issues if "naming-struct" in i.rule_id]
        assert len(struct_issues) == 1

    def test_go_function_camel_case(self, go_rules):
        lines = ["func MyFunction() {"]
        issues = check_naming_conventions(lines, go_rules, "test.go")
        fn_issues = [i for i in issues if "naming-function" in i.rule_id]
        assert len(fn_issues) == 0

    def test_go_package_lowercase(self, go_rules):
        lines = ["package mypackage"]
        issues = check_naming_conventions(lines, go_rules, "test.go")
        pkg_issues = [i for i in issues if "naming-package" in i.rule_id]
        assert len(pkg_issues) == 0

    def test_go_package_bad_name(self, go_rules):
        lines = ["package MyPackage"]
        issues = check_naming_conventions(lines, go_rules, "test.go")
        pkg_issues = [i for i in issues if "naming-package" in i.rule_id]
        assert len(pkg_issues) == 1

    def test_ts_function_camel_case(self, ts_rules):
        lines = ["export function myFunction() {"]
        issues = check_naming_conventions(lines, ts_rules, "test.ts")
        fn_issues = [i for i in issues if "naming-function" in i.rule_id]
        assert len(fn_issues) == 0

    def test_ts_class_pascal_case(self, ts_rules):
        lines = ["export class MyClass {"]
        issues = check_naming_conventions(lines, ts_rules, "test.ts")
        class_issues = [i for i in issues if "naming-class" in i.rule_id]
        assert len(class_issues) == 0

    def test_skip_comments_in_naming(self, python_rules):
        lines = ["# def BadName(): pass"]
        issues = check_naming_conventions(lines, python_rules, "test.py")
        assert len(issues) == 0


# ──────────────────────────────────────────────────────────
# Threshold tests
# ──────────────────────────────────────────────────────────


class TestThresholds:
    def test_line_length_detected(self, python_rules):
        lines = ["x = " + "a" * 130]
        issues = check_thresholds(lines, python_rules, "test.py")
        line_issues = [i for i in issues if "line-length" in i.rule_id]
        assert len(line_issues) == 1

    def test_line_length_ok(self, python_rules):
        lines = ["x = 'short'"]
        issues = check_thresholds(lines, python_rules, "test.py")
        line_issues = [i for i in issues if "line-length" in i.rule_id]
        assert len(line_issues) == 0

    def test_file_length_detected(self, python_rules):
        lines = [f"line_{i}" for i in range(600)]
        issues = check_thresholds(lines, python_rules, "test.py")
        file_issues = [i for i in issues if "file-length" in i.rule_id]
        assert len(file_issues) == 1

    def test_file_length_ok(self, python_rules):
        lines = [f"line_{i}" for i in range(100)]
        issues = check_thresholds(lines, python_rules, "test.py")
        file_issues = [i for i in issues if "file-length" in i.rule_id]
        assert len(file_issues) == 0

    def test_function_length_detected(self, python_rules):
        lines = ["def long_function():"] + ["    x = 1"] * 60
        issues = check_thresholds(lines, python_rules, "test.py")
        func_issues = [i for i in issues if "func-length" in i.rule_id]
        assert len(func_issues) == 1

    def test_nesting_depth_detected(self, python_rules):
        # Python indentation-based nesting
        lines = [
            "def f():",
            "    if True:",
            "        for i in range(10):",
            "            if i > 5:",
            "                while True:",
            "                    pass",
        ]
        issues = check_thresholds(lines, python_rules, "test.py")
        nest_issues = [i for i in issues if "nesting" in i.rule_id]
        assert len(nest_issues) == 1


# ──────────────────────────────────────────────────────────
# Max nesting depth helper
# ──────────────────────────────────────────────────────────


class TestNestingDepth:
    def test_flat_code(self):
        assert _max_nesting_depth(["x = 1"]) == 0

    def test_one_level(self):
        assert _max_nesting_depth(["if True:", "    x = 1"]) == 0

    def test_brackets(self):
        lines = ["result = func("]
        depth = _max_nesting_depth(lines)
        assert depth >= 1

    def test_nested_brackets(self):
        lines = ["result = func(a, inner("]
        depth = _max_nesting_depth(lines)
        assert depth >= 2

    def test_python_indent_depth(self):
        lines = [
            "def f():",
            "    if True:",
            "        for i in range(10):",
            "            if i > 5:",
            "                while True:",
            "                    pass",
        ]
        depth = _max_python_indent_depth(lines)
        assert depth == 5  # 20 spaces / 4 = 5


# ──────────────────────────────────────────────────────────
# Python AST tests
# ──────────────────────────────────────────────────────────


class TestPythonAST:
    def test_syntax_error_detected(self, tmp_dir):
        filepath = tmp_dir / "bad.py"
        filepath.write_text("def f(\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) >= 1

    def test_missing_return_type(self, tmp_dir):
        filepath = tmp_dir / "no_type.py"
        filepath.write_text("def public_func():\n    return 1\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-no-return-type" in ids

    def test_private_func_no_type_ok(self, tmp_dir):
        filepath = tmp_dir / "priv.py"
        filepath.write_text("def _private():\n    return 1\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        type_issues = [i for i in issues if i.rule_id == "py-ast-no-return-type"]
        assert len(type_issues) == 0

    def test_missing_param_type(self, tmp_dir):
        filepath = tmp_dir / "no_param.py"
        filepath.write_text("def f(x: int, y) -> int:\n    return x\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-no-param-type" in ids

    def test_self_param_not_checked(self, tmp_dir):
        filepath = tmp_dir / "cls.py"
        filepath.write_text("class A:\n    def method(self) -> None:\n        pass\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        param_issues = [i for i in issues if i.rule_id == "py-ast-no-param-type"]
        assert len(param_issues) == 0

    def test_function_too_long(self, tmp_dir):
        filepath = tmp_dir / "long.py"
        body = "\n".join(["    x = 1"] * 60)
        filepath.write_text(f"def long_func():\n{body}\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-function-length" in ids

    def test_too_many_args(self, tmp_dir):
        filepath = tmp_dir / "args.py"
        filepath.write_text("def f(a, b, c, d, e, f, g, h) -> int:\n    return 1\n")
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-function-args" in ids

    def test_cyclomatic_complexity(self, tmp_dir):
        filepath = tmp_dir / "complex.py"
        filepath.write_text(
            "def complex_func(x: int) -> int:\n"
            "    if x > 0:\n"
            "        if x > 10:\n"
            "            for i in range(x):\n"
            "                if i % 2 == 0:\n"
            "                    while i > 0:\n"
            "                        i -= 1\n"
            "                elif i % 3 == 0:\n"
            "                    pass\n"
            "                elif i % 5 == 0:\n"
            "                    pass\n"
            "                elif i % 7 == 0:\n"
            "                    pass\n"
            "                elif i % 11 == 0:\n"
            "                    pass\n"
            "    return x\n"
        )
        issues = check_python_ast(str(filepath), filepath.read_text().splitlines())
        ids = [i.rule_id for i in issues]
        assert "py-ast-complexity" in ids


class TestCyclomaticComplexity:
    def test_simple_function(self, tmp_dir):
        filepath = tmp_dir / "simple.py"
        filepath.write_text("def f():\n    return 1\n")
        tree = __import__("ast").parse(filepath.read_text())
        func = tree.body[0]
        assert _calc_cyclomatic_complexity(func) == 1

    def test_if_branches(self, tmp_dir):
        filepath = tmp_dir / "branch.py"
        filepath.write_text(
            "def f(x):\n    if x > 0:\n        return 1\n    elif x < 0:\n        return -1\n    return 0\n"
        )
        tree = __import__("ast").parse(filepath.read_text())
        func = tree.body[0]
        c = _calc_cyclomatic_complexity(func)
        assert c >= 3  # base + 2 branches


# ──────────────────────────────────────────────────────────
# Language detection tests
# ──────────────────────────────────────────────────────────


class TestLanguageDetection:
    def test_python_detection(self):
        assert detect_language_from_file(Path("main.py")) == "python"
        assert detect_language_from_file(Path("utils.pyi")) == "python"

    def test_typescript_detection(self):
        assert detect_language_from_file(Path("app.ts")) == "typescript"
        assert detect_language_from_file(Path("page.tsx")) == "typescript"

    def test_rust_detection(self):
        assert detect_language_from_file(Path("main.rs")) == "rust"

    def test_go_detection(self):
        assert detect_language_from_file(Path("main.go")) == "go"

    def test_unknown_extension(self):
        assert detect_language_from_file(Path("data.xyz")) is None


# ──────────────────────────────────────────────────────────
# Full file validation tests
# ──────────────────────────────────────────────────────────


class TestFileValidation:
    def test_validate_clean_python_file(self, tmp_dir):
        filepath = tmp_dir / "clean.py"
        filepath.write_text(
            '"""Clean module."""\n'
            "\n"
            "import logging\n"
            "\n"
            "logger = logging.getLogger(__name__)\n"
            "\n"
            "\n"
            "def add(a: int, b: int) -> int:\n"
            '    """Add two numbers."""\n'
            "    return a + b\n"
            "\n"
            "\n"
            "def process(items: list[int]) -> list[int]:\n"
            '    """Process items."""\n'
            "    return [x * 2 for x in items]\n"
        )
        result = validate_file(filepath, "python")
        # Should have no errors
        assert result.error_count == 0
        assert result.language == "python"

    def test_validate_dirty_python_file(self, tmp_dir):
        filepath = tmp_dir / "dirty.py"
        filepath.write_text(
            "import os\n"
            "from os import *\n"
            "\n"
            "def MyFunction(data: any):\n"
            "    try:\n"
            "        eval(data)\n"
            "    except:\n"
            "        pass\n"
            "\n"
            'password = "secret123"\n'
        )
        result = validate_file(filepath, "python")
        assert result.error_count > 0
        ids = [i.rule_id for i in result.issues]
        assert "py-star-import" in ids
        assert "py-eval-exec" in ids
        assert "py-bare-except" in ids

    def test_validate_clean_typescript(self, tmp_dir):
        filepath = tmp_dir / "clean.ts"
        filepath.write_text(
            "interface User {\n"
            "    name: string;\n"
            "    age: number;\n"
            "}\n"
            "\n"
            "export function greet(user: User): string {\n"
            "    return `Hello, ${user.name}`;\n"
            "}\n"
        )
        result = validate_file(filepath, "typescript")
        assert result.error_count == 0

    def test_validate_dirty_typescript(self, tmp_dir):
        filepath = tmp_dir / "dirty.ts"
        filepath.write_text(
            "var data: any = {};\n"
            "\n"
            "function process(input: any): any {\n"
            "    try {\n"
            "        return eval(input);\n"
            "    } catch (error) {}\n"
            "}\n"
        )
        result = validate_file(filepath, "typescript")
        assert result.error_count > 0
        ids = [i.rule_id for i in result.issues]
        assert "ts-any-type" in ids
        assert "ts-empty-catch" in ids

    def test_validate_clean_rust(self, tmp_dir):
        filepath = tmp_dir / "clean.rs"
        filepath.write_text(
            "use std::error::Error;\n"
            "\n"
            "pub fn process(data: &[u8]) -> Result<Vec<u8>, Box<dyn Error>> {\n"
            "    let result = data.iter().map(|b| b.wrapping_add(1)).collect();\n"
            "    Ok(result)\n"
            "}\n"
        )
        result = validate_file(filepath, "rust")
        assert result.error_count == 0

    def test_validate_dirty_rust(self, tmp_dir):
        filepath = tmp_dir / "dirty.rs"
        filepath.write_text(
            "fn process(data: &[u8]) -> Vec<u8> {\n"
            "    let x = data[0].unwrap();\n"
            "    let y = vec![1, 2, 3];\n"
            '    println!("{:?}", y);\n'
            '    panic!("oops");\n'
            "}\n"
        )
        result = validate_file(filepath, "rust")
        assert result.error_count > 0

    def test_validate_clean_go(self, tmp_dir):
        filepath = tmp_dir / "clean.go"
        filepath.write_text(
            "package main\n"
            "\n"
            'import "fmt"\n'
            "\n"
            "func process(data []byte) ([]byte, error) {\n"
            "    if len(data) == 0 {\n"
            '        return nil, fmt.Errorf("empty data")\n'
            "    }\n"
            "    result := make([]byte, len(data))\n"
            "    copy(result, data)\n"
            "    return result, nil\n"
            "}\n"
        )
        result = validate_file(filepath, "go")
        assert result.error_count == 0

    def test_validate_dirty_go(self, tmp_dir):
        filepath = tmp_dir / "dirty.go"
        filepath.write_text(
            "package main\n"
            "\n"
            'import "fmt"\n'
            "\n"
            "func process(data []byte) []byte {\n"
            "    result, _ := doSomething()\n"
            '    panic("not implemented")\n'
            "    fmt.Println(result)\n"
            "    return nil\n"
            "}\n"
        )
        result = validate_file(filepath, "go")
        assert result.error_count > 0

    def test_unreadable_file(self, tmp_dir):
        filepath = tmp_dir / "nonexistent.py"
        result = validate_file(filepath, "python")
        assert result.error_count > 0


# ──────────────────────────────────────────────────────────
# Directory validation tests
# ──────────────────────────────────────────────────────────


class TestDirectoryValidation:
    def test_validate_directory(self, tmp_dir):
        # Create test files
        (tmp_dir / "clean.py").write_text("def f() -> int:\n    return 1\n")
        (tmp_dir / "dirty.py").write_text("except:\n    pass\n")

        results = validate_directory(tmp_dir, language="python")
        assert len(results) == 2

        clean = [r for r in results if "clean" in r.file]
        dirty = [r for r in results if "dirty" in r.file]
        assert clean[0].error_count == 0
        assert dirty[0].error_count > 0

    def test_validate_directory_auto_detect(self, tmp_dir):
        (tmp_dir / "app.py").write_text("x = 1\n")
        (tmp_dir / "lib.rs").write_text("fn main() {}\n")

        results = validate_directory(tmp_dir)
        assert len(results) == 2
        languages = {r.language for r in results}
        assert "python" in languages
        assert "rust" in languages

    def test_exclude_directories(self, tmp_dir):
        node_modules = tmp_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "dep.js").write_text("var x = any;")

        (tmp_dir / "app.py").write_text("x = 1\n")

        results = validate_directory(tmp_dir)
        assert len(results) == 1
        assert "app.py" in results[0].file


# ──────────────────────────────────────────────────────────
# Function line extraction tests
# ──────────────────────────────────────────────────────────


class TestFunctionExtraction:
    def test_extract_python_functions(self):
        lines = [
            "def f1():",
            "    pass",
            "",
            "def f2():",
            "    x = 1",
            "    return x",
        ]
        funcs = _extract_function_lines(lines, "python")
        names = [f[0] for f in funcs]
        assert "f1" in names
        assert "f2" in names

    def test_extract_rust_functions(self):
        lines = [
            "pub fn my_function() {",
            "    let x = 1;",
            "}",
        ]
        funcs = _extract_function_lines(lines, "rust")
        names = [f[0] for f in funcs]
        assert "my_function" in names

    def test_extract_go_functions(self):
        lines = [
            "func MyFunction() {",
            "    x := 1",
            "    _ = x",
            "}",
        ]
        funcs = _extract_function_lines(lines, "go")
        names = [f[0] for f in funcs]
        assert "MyFunction" in names


# ──────────────────────────────────────────────────────────
# JSON output tests
# ──────────────────────────────────────────────────────────


class TestJsonOutput:
    def test_result_to_json(self, tmp_dir):
        filepath = tmp_dir / "test.py"
        filepath.write_text("except:\n    pass\n")
        result = validate_file(filepath, "python")
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert "py-bare-except" in json_str


# =====================================================================
