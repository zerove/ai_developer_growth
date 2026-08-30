#!/usr/bin/env python3
"""Rule Authoring CLI (#6): interactive rule creation with validation.

Creates properly structured YAML rule files with validation.

Usage:
    python tools/scripts/rule_author.py init --lang mylang
    python tools/scripts/rule_author.py add-rule --lang python --category anti_patterns
    python tools/scripts/rule_author.py validate --file my-rules.yml
    python tools/scripts/rule_author.py scaffold --lang python
    python tools/scripts/rule_author.py template --category anti_patterns
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import handle_error
from tools.scripts._common import rules_dir as _rules_dir

# Rule templates for each category
TEMPLATES = {
    "anti_patterns": {
        "description": "Code patterns that should be avoided",
        "fields": [
            "id",
            "name",
            "severity",
            "category",
            "pattern",
            "message",
            "fix_hint",
        ],
        "example": {
            "id": "py-bare-except",
            "name": "Bare except clause",
            "severity": "error",
            "category": "error_handling",
            "pattern": "except\\s*:",
            "message": "Avoid bare except: use specific exception types",
            "fix_hint": "Replace 'except:' with 'except SpecificException:'",
        },
    },
    "naming_conventions": {
        "description": "Naming rules for functions, classes, variables",
        "fields": ["id", "name", "severity", "pattern", "message", "applies_to"],
        "example": {
            "id": "py-function-name",
            "name": "Function naming convention",
            "severity": "warning",
            "pattern": "^def [a-z][a-z0-9_]*\\(",
            "message": "Functions should use snake_case",
            "applies_to": "function",
        },
    },
    "complexity": {
        "description": "Code complexity limits",
        "fields": ["id", "name", "severity", "metric", "max_value", "message"],
        "example": {
            "id": "py-function-length",
            "name": "Function too long",
            "severity": "warning",
            "metric": "function_length",
            "max_value": 50,
            "message": "Functions should be under 50 lines",
        },
    },
}

SEVERITY_LEVELS = ["error", "warning", "info"]
CATEGORY_TYPES = [
    "security",
    "error_handling",
    "type_safety",
    "code_quality",
    "naming",
    "performance",
    "style",
]


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new language rule directory."""
    lang = args.lang
    lang_dir = _rules_dir() / "languages" / lang
    rules_dir = lang_dir / "rules.d"

    if rules_dir.exists() and not args.force:
        print(f"Rules already exist for '{lang}' at {rules_dir}")
        print("Use --force to overwrite")
        return

    rules_dir.mkdir(parents=True, exist_ok=True)

    # Create base anti_patterns.yml
    base = {
        "language": lang,
        "version": ">=1.0",
        "config_version": "1.0",
        "anti_patterns": [],
        "naming_conventions": [],
        "complexity": [],
    }

    with open(rules_dir / "anti_patterns.yml", "w") as f:
        yaml.dump(base, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Initialized rule directory for '{lang}' at {rules_dir}")
    print(f"Created: {rules_dir / 'anti_patterns.yml'}")


def _get_rule_details(args: argparse.Namespace, lang: str) -> dict[str, str] | None:
    """Get rule details from args or interactive input.

    V2.21 P5-4 拆分: 抽 _prompt_or_value 收口 args.X or input(prompt) 模式,
    _prompt_required 收口必填字段 + None 返回 (rule_id/name/message),
    主函数仅 3 段委托.
    """
    rule_id = _prompt_required(args.id, f"Rule ID (e.g., {lang}-my-rule): ", "Rule ID is required")
    if rule_id is None:
        return None

    name, message = _prompt_required_pair(args.name, args.message, "Name and message are required")
    if name is None or message is None:
        return None

    severity = _prompt_or_value(args.severity, f"Severity ({'/'.join(SEVERITY_LEVELS)}): ") or "warning"
    pattern = _prompt_or_value(args.pattern, "Regex pattern (leave empty for non-pattern rules): ")
    fix_hint = _prompt_or_value(args.fix_hint, "Fix hint (optional): ")

    return {
        "id": rule_id,
        "name": name,
        "severity": severity,
        "message": message,
        "pattern": pattern,
        "fix_hint": fix_hint,
    }


def _prompt_or_value(arg_value: str | None, prompt: str) -> str:
    """若 arg_value 非空则返回, 否则 input(prompt).strip() (模块级 helper).

    Args:
        arg_value: 命令行参数值 (可能为空)
        prompt: input 提示文本

    Returns:
        优先 arg_value, 否则 input 去除首尾空白
    """
    if arg_value:
        return arg_value
    return input(prompt).strip()


def _prompt_required(arg_value: str | None, prompt: str, error_msg: str) -> str | None:
    """若 arg_value 为空则 input, 空字符串返回 None (模块级 helper).

    Args:
        arg_value: 命令行参数值
        prompt: input 提示文本
        error_msg: 必填为空时的错误消息

    Returns:
        值字符串, 若必填为空则 None
    """
    value = _prompt_or_value(arg_value, prompt)
    if not value:
        print(error_msg)
        return None
    return value


def _prompt_required_pair(
    name_arg: str | None, message_arg: str | None, error_msg: str
) -> tuple[str | None, str | None]:
    """批量获取 name + message 两个必填字段 (模块级 helper).

    Args:
        name_arg: name 命令行参数
        message_arg: message 命令行参数
        error_msg: 任一为空时的错误消息

    Returns:
        (name, message) 元组, 任一为空则都返回 None
    """
    name = _prompt_or_value(name_arg, "Rule name: ")
    message = _prompt_or_value(message_arg, "Message: ")
    if not name or not message:
        print(error_msg)
        return None, None
    return name, message


def _validate_pattern(pattern: str) -> bool:
    """Validate regex pattern."""
    if pattern:
        try:
            re.compile(pattern)
        except re.error as e:
            print(f"Invalid regex pattern: {e}")
            return False
    return True


def _check_duplicate_id(data: dict[str, Any], rule_id: str) -> bool:
    """Check if rule ID already exists."""
    existing_ids = set()
    for cat in ["anti_patterns", "naming_conventions", "complexity"]:
        for existing_rule in data.get(cat, []):
            existing_ids.add(existing_rule.get("id", ""))

    if rule_id in existing_ids:
        print(f"Rule '{rule_id}' already exists. Use a different ID.")
        return True
    return False


def _build_rule(rule_details: dict[str, str]) -> dict[str, Any]:
    """Build rule dict from details."""
    new_rule: dict[str, Any] = {
        "id": rule_details["id"],
        "name": rule_details["name"],
        "severity": rule_details["severity"],
    }
    if rule_details["pattern"]:
        new_rule["pattern"] = rule_details["pattern"]
    if rule_details["message"]:
        new_rule["message"] = rule_details["message"]
    if rule_details["fix_hint"]:
        new_rule["fix_hint"] = rule_details["fix_hint"]
    return new_rule


def cmd_add_rule(args: argparse.Namespace) -> None:
    """Add a new rule to a language's rule file (V2.21 P5-11 拆分: 抽 _save_rule_file)."""
    lang = args.lang
    category = args.category

    if category not in TEMPLATES:
        print(f"Unknown category: {category}")
        print(f"Available: {', '.join(TEMPLATES.keys())}")
        return

    rules_file = _rules_dir() / "languages" / lang / "rules.d" / "anti_patterns.yml"

    if not rules_file.exists():
        print(f"Rule file not found: {rules_file}")
        print(f"Run: python rule_author.py init --lang {lang}")
        return

    with open(rules_file) as f:
        data = yaml.safe_load(f) or {}

    # Get rule details
    rule_details = _get_rule_details(args, lang)
    if not rule_details:
        return

    # Validate pattern
    if not _validate_pattern(rule_details["pattern"]):
        return

    # Check for duplicate ID
    if _check_duplicate_id(data, rule_details["id"]):
        return

    # Build and add rule
    new_rule = _build_rule(rule_details)
    if category not in data:
        data[category] = []
    data[category].append(new_rule)

    _save_rule_file(rules_file, data, rule_details, category)


def _save_rule_file(rules_file: Path, data: dict[str, Any], rule_details: dict[str, Any], category: str) -> None:
    """保存规则到 YAML 文件 + 打印成功消息 (模块级 helper).

    Args:
        rules_file: 规则 YAML 路径
        data: 更新后 data 字典
        rule_details: 规则详情
        category: 规则类别
    """
    with open(rules_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Added rule '{rule_details['id']}' to {category}")
    print(f"  severity: {rule_details['severity']}")
    if rule_details["pattern"]:
        print(f"  pattern: {rule_details['pattern']}")
    print(f"  message: {rule_details['message']}")


def _validate_single_rule(category: str, rule: dict[str, Any], rule_id: str) -> tuple[int, int]:
    """Validate a single rule. Returns (errors, warnings).

    V2.21 P5-5 拆分: 抽 _check_required_fields 收口 3 必填守卫 + severity 验证,
    _check_pattern 收口 pattern 正则编译,
    _check_test_cases 收口 test_cases 遍历 + 2 必填守卫,
    主函数仅 type 守卫 + 委托.
    """
    if not isinstance(rule, dict):
        print(f"  ✗ {category}: rule is not a dict")
        return 1, 0

    errors = _check_required_fields(category, rule)
    errors += _check_pattern(category, rule)
    _, warnings = _check_name(category, rule)
    errors += _check_test_cases(category, rule)

    return errors, warnings


def _check_required_fields(category: str, rule: dict[str, Any]) -> int:
    """检查 id + severity 必填字段 (模块级 helper).

    Args:
        category: 类别名
        rule: rule dict

    Returns:
        错误数
    """
    errors = 0
    if not rule.get("id"):
        print(f"  ✗ {category}: rule missing 'id'")
        errors += 1
    if not rule.get("severity"):
        print(f"  ✗ {category}/{rule.get('id', '?')}: missing 'severity'")
        errors += 1
    elif rule["severity"] not in SEVERITY_LEVELS:
        print(f"  ✗ {category}/{rule['id']}: invalid severity '{rule['severity']}'")
        errors += 1
    return errors


def _check_name(category: str, rule: dict[str, Any]) -> tuple[int, int]:
    """检查 name 必填字段 (warning, 模块级 helper).

    Args:
        category: 类别名
        rule: rule dict

    Returns:
        (errors, warnings) 元组 (name 缺失只增加 warnings)
    """
    if not rule.get("name"):
        print(f"  ✗ {category}/{rule.get('id', '?')}: missing 'name'")
        return 0, 1
    return 0, 0


def _check_pattern(category: str, rule: dict[str, Any]) -> int:
    """检查 pattern 正则编译 (模块级 helper).

    Args:
        category: 类别名
        rule: rule dict

    Returns:
        错误数 (0 if 无 pattern 或 pattern 合法)
    """
    if "pattern" not in rule:
        return 0
    try:
        re.compile(rule["pattern"])
    except re.error as e:
        print(f"  ✗ {category}/{rule['id']}: invalid regex: {e}")
        return 1
    return 0


def _check_test_cases(category: str, rule: dict[str, Any]) -> int:
    """遍历 test_cases 检查 code + should_match 必填 (模块级 helper).

    Args:
        category: 类别名
        rule: rule dict

    Returns:
        错误数
    """
    errors = 0
    for i, tc in enumerate(rule.get("test_cases", [])):
        if "code" not in tc:
            print(f"  ✗ {category}/{rule['id']}/test[{i}]: missing 'code'")
            errors += 1
        if "should_match" not in tc:
            print(f"  ✗ {category}/{rule['id']}/test[{i}]: missing 'should_match'")
            errors += 1
    return errors


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate a rule YAML file (V2.21 P5-10 拆分: 抽 _load_rule_file + _summarize_validation)."""
    filepath = Path(args.file)
    data = _load_rule_file(filepath)
    if data is None:
        return

    errors = 0
    warnings = 0
    if "language" not in data:
        print("  ✗ Missing 'language' field")
        errors += 1

    for category in ["anti_patterns", "naming_conventions", "complexity"]:
        for rule in data.get(category, []):
            if not isinstance(rule, dict):
                print(f"  ✗ Rule in {category} is not a dictionary: {rule}")
                errors += 1
                continue
            rule_errors, rule_warnings = _validate_single_rule(category, rule, rule.get("id", "?"))
            errors += rule_errors
            warnings += rule_warnings

    _summarize_validation(data, errors, warnings)


def _load_rule_file(filepath: Path) -> dict[str, Any] | None:
    """读取 + 校验 YAML 文件存在性 + 解析 (模块级 helper).

    Args:
        filepath: 规则 YAML 路径

    Returns:
        解析后的 data 字典, 文件不存在或 YAML 无效返回 None
    """
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return None

    with open(filepath) as f:
        data = yaml.safe_load(f)

    if not data:
        print(f"Invalid YAML: {filepath}")
        return None
    return data


def _summarize_validation(data: dict[str, Any], errors: int, warnings: int) -> None:
    """汇总校验结果并打印 (模块级 helper).

    Args:
        data: 规则字典
        errors: 错误计数
        warnings: 警告计数
    """
    if errors == 0 and warnings == 0:
        total_rules = sum(len(data.get(c, [])) for c in ["anti_patterns", "naming_conventions", "complexity"])
        print(f"  ✓ Valid ({total_rules} rules)")
    else:
        print(f"\n  {errors} errors, {warnings} warnings")


def cmd_scaffold(args: argparse.Namespace) -> None:
    """Scaffold a complete rule set for a language."""
    lang = args.lang
    lang_dir = _rules_dir() / "languages" / lang
    rules_dir = lang_dir / "rules.d"
    rules_dir.mkdir(parents=True, exist_ok=True)

    for category, template in TEMPLATES.items():
        data = {
            "language": lang,
            "version": ">=1.0",
            "config_version": "1.0",
            category: [template["example"]],
        }

        filepath = rules_dir / "anti_patterns.yml"
        if filepath.exists():
            with open(filepath) as f:
                existing = yaml.safe_load(f) or {}
            existing.setdefault(category, []).append(template["example"])
            data = existing

        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Scaffolded rule set for '{lang}' at {rules_dir}")
    print("  Created: anti_patterns.yml (with 1 example rule per category)")


def cmd_template(args: argparse.Namespace) -> None:
    """Show template for a category."""
    category = args.category
    if category not in TEMPLATES:
        print(f"Unknown category: {category}")
        print(f"Available: {', '.join(TEMPLATES.keys())}")
        return

    template = TEMPLATES[category]
    print(f"Category: {category}")
    print(f"Description: {template['description']}")
    print(f"Fields: {', '.join(template['fields'])}")
    print("\nExample:")
    print(yaml.dump(template["example"], default_flow_style=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule Authoring CLI: create and validate rules")
    sub = parser.add_subparsers(dest="command")

    init_p = sub.add_parser("init", help="Initialize rule directory")
    init_p.add_argument("--lang", type=str, required=True, help="Language name")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing")

    add_p = sub.add_parser("add-rule", help="Add a new rule")
    add_p.add_argument("--lang", type=str, required=True, help="Language")
    add_p.add_argument("--category", type=str, required=True, choices=list(TEMPLATES.keys()))
    add_p.add_argument("--id", type=str, help="Rule ID")
    add_p.add_argument("--name", type=str, help="Rule name")
    add_p.add_argument("--severity", type=str, choices=SEVERITY_LEVELS)
    add_p.add_argument("--pattern", type=str, help="Regex pattern")
    add_p.add_argument("--message", type=str, help="Rule message")
    add_p.add_argument("--fix-hint", type=str, help="Fix hint")

    val_p = sub.add_parser("validate", help="Validate rule file")
    val_p.add_argument("--file", type=str, required=True, help="YAML file to validate")

    sc_p = sub.add_parser("scaffold", help="Scaffold rule set")
    sc_p.add_argument("--lang", type=str, required=True, help="Language name")

    tmpl_p = sub.add_parser("template", help="Show category template")
    tmpl_p.add_argument("--category", type=str, required=True, choices=list(TEMPLATES.keys()))

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        commands = {
            "init": cmd_init,
            "add-rule": cmd_add_rule,
            "validate": cmd_validate,
            "scaffold": cmd_scaffold,
            "template": cmd_template,
        }

        commands[args.command](args)
        return 0
    except Exception as e:
        handle_error(e, script="rule_author")
        return 1


if __name__ == "__main__":
    sys.exit(main())
