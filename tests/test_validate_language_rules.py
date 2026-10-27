"""validate_language_rules 核心校验用例。

覆盖 Issue/ValidationResult/规则加载/anti-pattern/命名/阈值/嵌套/AST/
圈复杂度/语言检测/文件与目录校验/JSON 输出。

各语言 anti-pattern 规则用例见 test_language_rules_languages.py。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.scripts.validate_language_rules import (
    Issue,
    ValidationResult,
    check_anti_patterns,
    check_naming_conventions,
    load_rules,
)


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

    def test_eval_exec_not_duplicated_by_common_rule(self, python_rules):
        rule_ids = {r["id"] for r in python_rules["anti_patterns"]}
        assert "py-eval-exec" in rule_ids
        assert "common-eval-exec" not in rule_ids

        lines = ["result = eval(user_input)"]
        issues = check_anti_patterns(lines, python_rules, "test.py")
        eval_ids = [i.rule_id for i in issues if i.rule_id in {"py-eval-exec", "common-eval-exec"}]
        assert eval_ids == ["py-eval-exec"]

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
