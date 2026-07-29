"""
ADG 规则生成器 — 将 agent 生成的规则保存到标准位置

不调用任何 LLM API — Jcode agent 本身就是 LLM。
此模块只处理文件 I/O、验证和发现。

工作流:
  1. Jcode skill 调用 generate_rules()
  2. agent 提供规则内容（通过自身知识）
  3. 本模块验证 YAML 格式并写入缓存
  4. rule_loader / scan 自动发现新规则
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any


# ── 生成规则缓存目录 ──────────────────────────────────────

def get_generated_rules_dir() -> Path:
    """获取生成规则的缓存目录。

    优先级:
      1. ADG_HOME 环境变量
      2. ~/.config/adg/rules/generated/
    """
    base = Path(os.environ.get("ADG_HOME", Path.home() / ".config" / "adg"))
    return base / "rules" / "generated"


# ── 已知语言列表（用于验证语言名） ──────────────────────────

KNOWN_LANGUAGES: dict[str, str] = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "rust": "Rust",
    "go": "Go",
    "java": "Java",
    "kotlin": "Kotlin",
    "csharp": "C#",
    "cpp": "C++",
    "c": "C",
    "ruby": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "dart": "Dart",
    "scala": "Scala",
    "elixir": "Elixir",
    "clojure": "Clojure",
    "haskell": "Haskell",
    "lua": "Lua",
    "zig": "Zig",
    "mojo": "Mojo",
    "solidity": "Solidity",
    "r": "R",
    "matlab": "MATLAB",
    "perl": "Perl",
    "powershell": "PowerShell",
    "assembly": "Assembly",
    "fortran": "Fortran",
    "graphql": "GraphQL",
    "toml": "TOML",
    "markdown": "Markdown",
    "yaml": "YAML",
    "json": "JSON",
}

# 语言到文件扩展名映射（用于 skill 的自动检测）
LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py", ".pyi", ".pyx"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "kotlin": [".kt", ".kts"],
    "csharp": [".cs"],
    "cpp": [".cpp", ".cxx", ".cc", ".hpp"],
    "c": [".c", ".h"],
    "ruby": [".rb"],
    "php": [".php"],
    "swift": [".swift"],
    "dart": [".dart"],
    "scala": [".scala"],
    "elixir": [".ex", ".exs"],
    "clojure": [".clj", ".cljs"],
    "haskell": [".hs"],
    "lua": [".lua"],
    "zig": [".zig"],
    "mojo": [".mojo", ".🔥"],
    "solidity": [".sol"],
    "r": [".r", ".R"],
    "matlab": [".m"],
    "perl": [".pl", ".pm"],
    "powershell": [".ps1", ".psm1"],
    "assembly": [".asm", ".s"],
    "fortran": [".f", ".f90", ".f95"],
    "graphql": [".graphql", ".gql"],
    "toml": [".toml"],
    "markdown": [".md"],
    "yaml": [".yml", ".yaml"],
    "json": [".json"],
}

_EXT_TO_LANG = {ext: lang for lang, exts in LANGUAGE_EXTENSIONS.items() for ext in exts}


def detect_language_from_extension(filepath: str | Path) -> str | None:
    """从文件扩展名检测语言"""
    return _EXT_TO_LANG.get(Path(filepath).suffix.lower())


# ── 规则模板 ──────────────────────────────────────────────

RULE_TEMPLATE = '''\
language: {language}
version: '>=1.0'
config_version: '1.0'
generated_by: ai-dev-framework
description: >
  Auto-generated quality rules for {language}.
  These rules detect common anti-patterns, security issues,
  and code quality problems specific to {language}.

anti_patterns:
{patterns}
'''


def format_rules(language: str, rules: list[dict[str, Any]]) -> str:
    """将规则列表格式化为 YAML 字符串。

    Args:
        language: 语言名称（小写）
        rules: 规则字典列表，每项包含:
            - id: 规则 ID (如 "mojo-unsafe-cast")
            - name: 规则名称
            - severity: "error" / "warning" / "info"
            - category: 分类
            - pattern: 正则表达式
            - message: 问题描述
            - fix_hint (可选): 修复建议
            - exclude_files (可选): 排除文件列表
            - exclude_patterns (可选): 内容排除模式
            - test_cases (可选): 测试用例
    """
    import yaml

    # 构建规则 YAML
    rule_dicts = []
    for r in rules:
        rd = {
            "id": r["id"],
            "name": r["name"],
            "severity": r["severity"],
            "category": r["category"],
            "pattern": r["pattern"],
            "message": r["message"],
        }
        if r.get("fix_hint"):
            rd["fix_hint"] = r["fix_hint"]
        if r.get("exclude_files"):
            rd["exclude_files"] = r["exclude_files"]
        if r.get("exclude_patterns"):
            rd["exclude_patterns"] = r["exclude_patterns"]
        if r.get("test_cases"):
            rd["test_cases"] = r["test_cases"]
        rule_dicts.append(rd)

    patterns_yaml = yaml.dump(rule_dicts, default_flow_style=False, allow_unicode=True)
    # Indent for template insertion
    indented = "\n".join("  " + line if line.strip() else "" for line in patterns_yaml.split("\n"))

    return RULE_TEMPLATE.format(language=language, patterns=indented)


# ── 规则保存 ──────────────────────────────────────────────

def save_rules(language: str, rules: list[dict[str, Any]], force: bool = False) -> Path:
    """保存生成的规则到缓存目录。

    Args:
        language: 语言名称
        rules: 规则列表（同 format_rules 格式）
        force: 是否覆盖已有规则

    Returns:
        保存的文件路径

    Raises:
        FileExistsError: 规则已存在且 force=False
        ValueError: 语言名无效或规则列表为空
    """
    lang = language.lower().strip()
    if lang not in KNOWN_LANGUAGES:
        raise ValueError(f"Unknown language: {language}. Known: {', '.join(sorted(KNOWN_LANGUAGES))}")
    if not rules:
        raise ValueError("At least one rule is required")

    gen_dir = get_generated_rules_dir()
    target = gen_dir / lang / "rules.d" / "anti_patterns.yml"

    if target.exists() and not force:
        raise FileExistsError(
            f"Rules already exist for '{language}': {target}\n"
            f"  Use --force to overwrite, or use 'adg-dev generate-rules {language} --force'"
        )

    target.parent.mkdir(parents=True, exist_ok=True)

    content = format_rules(lang, rules)
    target.write_text(content, encoding="utf-8")

    return target


# ── 规则发现 ──────────────────────────────────────────────

def discover_generated_rules() -> list[Path]:
    """发现所有已生成规则文件。"""
    gen_dir = get_generated_rules_dir()
    if not gen_dir.exists():
        return []
    return sorted(gen_dir.glob("*/rules.d/anti_patterns.yml"))


def load_generated_rules(language: str) -> list[dict[str, Any]]:
    """加载指定语言的生成规则。

    Args:
        language: 语言名称

    Returns:
        规则列表，如无则返回空列表
    """
    gen_dir = get_generated_rules_dir()
    rule_file = gen_dir / language / "rules.d" / "anti_patterns.yml"
    if not rule_file.exists():
        return []

    try:
        import yaml
        data = yaml.safe_load(rule_file.read_text())
        if data and isinstance(data, dict):
            return data.get("anti_patterns", [])
    except Exception:
        _ = None  # generated rules are optional; skip malformed files
    return []


def list_generated_languages() -> list[str]:
    """列出已生成规则的语言。"""
    gen_dir = get_generated_rules_dir()
    if not gen_dir.exists():
        return []
    return sorted(d.name for d in gen_dir.iterdir() if d.is_dir() and (d / "rules.d" / "anti_patterns.yml").exists())


# ── 验证 ──────────────────────────────────────────────────

def validate_rules_yaml(content: str) -> list[str]:
    """验证 YAML 规则格式，返回错误列表。"""
    errors: list[str] = []

    try:
        import yaml
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["Root must be a dict with 'anti_patterns' key"]

    if "language" not in data:
        errors.append("Missing 'language' field")
    if "anti_patterns" not in data:
        errors.append("Missing 'anti_patterns' field")
        return errors

    patterns = data["anti_patterns"]
    if not isinstance(patterns, list):
        return ["'anti_patterns' must be a list"]

    seen_ids: set[str] = set()
    for i, rule in enumerate(patterns):
        if not isinstance(rule, dict):
            errors.append(f"Rule #{i}: must be a dict")
            continue

        # 必需字段
        for field in ("id", "name", "severity", "category", "pattern", "message"):
            if field not in rule:
                errors.append(f"Rule #{i} ({rule.get('id', '?')}): missing '{field}'")

        rid = rule.get("id", "")
        if rid in seen_ids:
            errors.append(f"Duplicate rule ID: {rid}")
        seen_ids.add(rid)

        # 验证 severity
        if rule.get("severity") not in ("error", "warning", "info"):
            errors.append(f"Rule '{rid}': severity must be error/warning/info")

        # 验证正则合法性
        try:
            re.compile(rule.get("pattern", ""))
        except re.error as e:
            errors.append(f"Rule '{rid}': invalid regex pattern: {e}")

    return errors


# ── CLI ──────────────────────────────────────────────────

def print_status(language: str | None = None) -> None:
    """打印生成规则的状态。"""
    gen_langs = list_generated_languages()
    _out = sys.stdout

    if not gen_langs:
        _out.write("📭 No generated rules found.\n")
        _out.write(f"   Cache directory: {get_generated_rules_dir()}\n")
        _out.write("   Use 'adg-dev generate-rules <language> [--file sample.ext]' to generate.\n")
        return

    _out.write(f"📦 Generated rules ({len(gen_langs)} languages):\n")
    for lang in gen_langs:
        rules = load_generated_rules(lang)
        errors = sum(1 for r in rules if r.get("severity") == "error")
        warnings = sum(1 for r in rules if r.get("severity") == "warning")
        info = sum(1 for r in rules if r.get("severity") == "info")
        _out.write(f"  {lang}: {len(rules)} rules ({errors}e/{warnings}w/{info}i)\n")

    if language:
        rules = load_generated_rules(language)
        if rules:
            _out.write(f"\n  Details for '{language}':\n")
            for r in rules:
                icon = {"error": "🔴", "warning": "🟡", "info": "ℹ️"}.get(r.get("severity", ""), "•")
                _out.write(f"    {icon} [{r.get('id','')}] {r.get('message','')}\n")
        else:
            _out.write(f"\n  No generated rules for '{language}'\n")

    _out.write(f"\n  Cache: {get_generated_rules_dir()}\n")


if __name__ == "__main__":
    # 简单的 CLI 状态查看
    lang = sys.argv[1] if len(sys.argv) > 1 else None
    print_status(lang)
