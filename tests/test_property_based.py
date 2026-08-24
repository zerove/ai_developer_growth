"""Property-based tests for rules_engine using Hypothesis.

Tests invariants and properties that should hold for all valid inputs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import characters

from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns
from tools.scripts.rules_engine.complexity_checker import check_python_complexity
from tools.scripts.rules_engine.models import Issue
from tools.scripts.rules_engine.naming_checker import check_naming_conventions

# ── 策略定义 ──

# 有效的 Python 标识符
valid_python_identifier = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]*", fullmatch=True)

# Python 代码片段策略
python_code_snippets = st.one_of(
    st.just(""),
    st.just("pass"),
    st.just("x = 1"),
    st.just("def foo():\n    pass"),
    st.just("class Foo:\n    pass"),
    st.just("if True:\n    pass"),
    st.just("for i in range(10):\n    pass"),
    st.just("try:\n    pass\nexcept:\n    pass"),
    st.just("eval('x')"),
    st.just("exec('x')"),
    st.just("import os\nos.system('ls')"),
    st.text(alphabet=characters(blacklist_categories=("Cc", "Cs")), min_size=0, max_size=200),
)

# 严重级别策略
severity_values = ["error", "warning", "info"]

# 默认规则 - check_anti_patterns 期望 anti_patterns 是列表
default_anti_pattern_rules = {
    "anti_patterns": [
        {
            "id": "bare-except",
            "pattern": r"except\s*:",
            "message": "Bare except clause",
            "severity": "warning",
        },
        {
            "id": "eval-exec",
            "pattern": r"\b(eval|exec)\s*\(",
            "message": "Use of eval/exec",
            "severity": "error",
        },
        {
            "id": "dangerous-functions",
            "pattern": r"\b(os\.system|subprocess\.call|subprocess\.run)\s*\(",
            "message": "Dangerous function call",
            "severity": "error",
        },
    ]
}

default_naming_rules = {
    "naming": {
        "function": {
            "pattern": "^[a-z_][a-z0-9_]*$",
            "message": "Function name should be snake_case",
            "severity": "warning",
        },
        "class": {
            "pattern": "^[A-Z][a-zA-Z0-9]*$",
            "message": "Class name should be PascalCase",
            "severity": "warning",
        },
    }
}

default_complexity_rules = {
    "thresholds": {
        "max_nesting_depth": 4,
        "max_cyclomatic_complexity": 10,
    }
}


# ── Anti-pattern 检查器属性测试 ──


@given(python_code_snippets)
@settings(max_examples=100, deadline=None)
def test_anti_patterns_returns_list(code: str) -> None:
    """check_anti_patterns 应该总是返回列表。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_anti_patterns(Path(f.name), "python", default_anti_pattern_rules)
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)
        assert hasattr(issue, "severity")
        assert hasattr(issue, "message")
        assert hasattr(issue, "line")


@given(python_code_snippets)
@settings(max_examples=50, deadline=None)
def test_anti_patterns_severity_valid(code: str) -> None:
    """所有返回的 issue 严重级别应该在有效值中。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_anti_patterns(Path(f.name), "python", default_anti_pattern_rules)
    for issue in issues:
        assert issue.severity in severity_values


@given(st.one_of(st.just("eval('x')"), st.just("exec('x')")))
@settings(max_examples=10, deadline=None)
def test_anti_patterns_detects_dangerous(code: str) -> None:
    """eval/exec 应该被检测为 dangerous 反模式。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_anti_patterns(Path(f.name), "python", default_anti_pattern_rules)
    dangerous_issues = [i for i in issues if i.rule_id == "eval-exec"]
    assert len(dangerous_issues) > 0


# ── 命名约定检查器属性测试 ──


@given(python_code_snippets)
@settings(max_examples=100, deadline=None)
def test_naming_returns_list(code: str) -> None:
    """check_naming_conventions 应该总是返回列表。"""
    lines = code.splitlines()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_naming_conventions(lines, default_naming_rules, f.name, "python")
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)


@given(valid_python_identifier)
@settings(max_examples=50, deadline=None)
def test_naming_snake_case_functions(identifier: str) -> None:
    """snake_case 函数名应该通过检查。"""
    code = f"def {identifier}():\n    pass"
    lines = code.splitlines()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_naming_conventions(lines, default_naming_rules, f.name, "python")
    naming_issues = [i for i in issues if "naming" in i.rule_id.lower()]
    # snake_case 应该没有命名问题
    if "_" in identifier or identifier.islower():
        assert len(naming_issues) == 0


# ── 复杂度检查器属性测试 ──


@given(python_code_snippets)
@settings(max_examples=100, deadline=None)
def test_complexity_returns_list(code: str) -> None:
    """check_python_complexity 应该总是返回列表。"""
    lines = code.splitlines()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_python_complexity(lines, default_complexity_rules, f.name)
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)


@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=20, deadline=None)
def test_complexity_nested_loops(depth: int) -> None:
    """嵌套循环深度超过阈值应该被检测。"""
    indent = "    "
    code_lines = ["def test_func():"]
    for i in range(depth):
        code_lines.append(f"{indent * (i + 1)}for i{i} in range(10):")
    code_lines.append(f"{indent * (depth + 1)}pass")
    code = "\n".join(code_lines)
    lines = code.splitlines()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_python_complexity(lines, default_complexity_rules, f.name)

    nesting_issues = [i for i in issues if "nesting" in i.rule_id.lower() or "depth" in i.message.lower()]
    if depth > 4:  # 默认阈值 max_nesting = 4
        assert len(nesting_issues) > 0


# ── Issue 模型属性测试 ──


@given(
    st.text(min_size=1, max_size=100),
    st.integers(min_value=1, max_value=1000),
    st.sampled_from(severity_values),
    st.text(min_size=1, max_size=200),
    st.text(min_size=1, max_size=50),
)
@settings(max_examples=100, deadline=None)
def test_issue_creation(rule_id: str, line: int, severity: str, message: str, category: str) -> None:
    """Issue 创建应该保持字段完整性。"""
    issue = Issue(
        rule_id=rule_id,
        severity=severity,
        category=category,
        file="test.py",
        line=line,
        message=message,
    )
    assert issue.rule_id == rule_id
    assert issue.line == line
    assert issue.severity == severity
    assert issue.message == message
    assert issue.category == category


@given(
    st.text(min_size=1, max_size=100),
    st.integers(min_value=1, max_value=1000),
    st.sampled_from(severity_values),
    st.text(min_size=1, max_size=200),
    st.text(min_size=1, max_size=50),
    st.sampled_from([None, "suggestion text"]),
)
@settings(max_examples=50, deadline=None)
def test_issue_with_fix_hint(
    rule_id: str,
    line: int,
    severity: str,
    message: str,
    category: str,
    fix_hint: str | None,
) -> None:
    """Issue 带修复建议创建应该正常工作。"""
    issue = Issue(
        rule_id=rule_id,
        severity=severity,
        category=category,
        file="test.py",
        line=line,
        message=message,
        fix_hint=fix_hint or "",
    )
    assert issue.fix_hint == (fix_hint or "")


# ── 空文件和边界情况 ──


@given(st.just(""))
@settings(max_examples=10, deadline=None)
def test_empty_file(code: str) -> None:
    """空文件不应该崩溃。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        issues = check_anti_patterns(Path(f.name), "python", default_anti_pattern_rules)
        lines = code.splitlines()
        issues.extend(check_naming_conventions(lines, default_naming_rules, f.name, "python"))
        issues.extend(check_python_complexity(lines, default_complexity_rules, f.name))
    assert isinstance(issues, list)


# ── Unicode 和特殊字符 ──


@given(
    st.text(
        alphabet=st.characters(
            min_codepoint=32,
            max_codepoint=65535,
            blacklist_categories=("Cc", "Cs"),
        ),
        min_size=0,
        max_size=100,
    )
)
@settings(max_examples=30, deadline=None)
def test_unicode_in_strings(code: str) -> None:
    """包含 Unicode 的字符串不应该导致崩溃。"""
    # 构造合法的 Python 代码：字符串字面量
    safe_code = f'"""{code}"""'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(safe_code)
        f.flush()
        issues = check_anti_patterns(Path(f.name), "python", default_anti_pattern_rules)
        lines = safe_code.splitlines()
        issues.extend(check_naming_conventions(lines, default_naming_rules, f.name, "python"))
        issues.extend(check_python_complexity(lines, default_complexity_rules, f.name))
    assert isinstance(issues, list)


# ── 单行和多行测试 ──


@given(st.integers(min_value=1, max_value=100))
@settings(max_examples=30, deadline=None)
def test_many_lines(lines_count: int) -> None:
    """大量重复行不应该崩溃。"""
    code = "x = 1"
    repeated_code = "\n".join([code] * lines_count)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(repeated_code)
        f.flush()
        issues = check_anti_patterns(Path(f.name), "python", default_anti_pattern_rules)
        lines = repeated_code.splitlines()
        issues.extend(check_naming_conventions(lines, default_naming_rules, f.name, "python"))
        issues.extend(check_python_complexity(lines, default_complexity_rules, f.name))
    assert isinstance(issues, list)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "--tb=short"])
