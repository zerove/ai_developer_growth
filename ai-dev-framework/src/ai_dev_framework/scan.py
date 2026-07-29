"""
adg scan — 文件级反模式扫描模块

读取文件，按语言加载 ADG 规则目录中的 anti-patterns，
自动应用 common/security.yml + universal.yml 跨语言规则。

Usage:
    from ai_dev_framework.scan import scan_file
    issues = scan_file("src/main.py")
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScanIssue:
    """扫描发现的问题"""

    file: str
    line: int
    column: int
    rule_id: str
    severity: str
    category: str
    message: str
    fix_hint: str = ""


@dataclass
class ScanResult:
    """扫描结果"""

    file: str
    language: str
    issues: list[ScanIssue] = field(default_factory=list)
    passed: bool = True
    error: str | None = None


# ── 语言检测 ──────────────────────────────────

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".scala": "scala",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".c": "cpp",
    ".h": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".dart": "dart",
    ".sh": "assembly",
    ".bash": "assembly",
    ".zsh": "assembly",
    ".lua": "lua",
    ".r": "r",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".hs": "haskell",
    ".zig": "zig",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".vue": "typescript",
    ".svelte": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}


def _detect_language(filepath: str | Path) -> str | None:
    """根据文件扩展名检测语言"""
    p = Path(filepath)
    return _EXTENSION_MAP.get(p.suffix.lower())


# ── 规则加载 ──────────────────────────────────

_RULES_HOME = Path(os.environ.get("ADG_HOME", Path.home() / ".config" / "adg"))

# 项目本地规则覆盖 — scan.py 所在项目下的 languages/ 目录
_script_dir = Path(__file__).resolve().parent.parent.parent
_PROJECT_LANGUAGES = _script_dir / "languages"


def _load_project_rules(lang: str) -> list[dict]:
    """加载项目本地规则覆盖（按 rule ID 覆盖用户级规则）"""
    project_path = _PROJECT_LANGUAGES / lang / "rules.d" / "anti_patterns.yml"
    if project_path.exists():
        return _load_yaml_rules(project_path)
    return []


def _merge_rules_with_overlay(base: list[dict], overlay: list[dict]) -> list[dict]:
    """合并规则列表：overlay 中同 ID 的规则替换 base 中的"""
    result: list[dict] = []
    overlay_ids: set[str] = set()

    for r in overlay:
        rid = r.get("id")
        if rid:
            overlay_ids.add(rid)
            # 替换 base 中同 ID 的规则
            replaced = False
            for i, br in enumerate(result):
                if br.get("id") == rid:
                    result[i] = r
                    replaced = True
                    break
            if not replaced:
                result.append(r)
        else:
            result.append(r)  # 无 ID 的 overlay 规则直接附加

    # 追加未被覆盖的 base 规则
    for r in base:
        rid = r.get("id")
        if rid not in overlay_ids:
            result.append(r)

    return result


def _load_yaml_rules(path: Path) -> list[dict]:
    """加载 YAML 规则文件，返回 anti_patterns 列表"""
    import yaml

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and isinstance(data, dict):
            return data.get("anti_patterns", [])
        return []
    except Exception:
        return []


def _load_rules_for_language(lang: str) -> list[dict]:
    """加载指定语言的规则 + 通用规则 + 生成规则 + 项目覆盖"""
    rules: list[dict] = []

    # 1. 语言特有规则
    lang_path = _RULES_HOME / "rules" / "languages" / lang / "rules.d" / "anti_patterns.yml"
    if lang_path.exists():
        rules.extend(_load_yaml_rules(lang_path))

    # 2. 生成规则 (来自 /generate-rules skill)
    generated_path = _RULES_HOME / "rules" / "generated" / lang / "rules.d" / "anti_patterns.yml"
    if generated_path.exists():
        generated_rules = _load_yaml_rules(generated_path)
        if generated_rules:
            rules.extend(generated_rules)

    # 3. 通用安全规则 (跨语言)
    security_path = _RULES_HOME / "rules" / "common" / "security.yml"
    if security_path.exists():
        rules.extend(_load_yaml_rules(security_path))

    # 4. 通用质量规则 (跨语言)
    universal_path = _RULES_HOME / "rules" / "common" / "universal.yml"
    if universal_path.exists():
        rules.extend(_load_yaml_rules(universal_path))

    # 5. 项目本地覆盖规则 (按 rule ID 覆盖以上规则)
    project_rules = _load_project_rules(lang)
    if project_rules:
        rules = _merge_rules_with_overlay(rules, project_rules)

    return rules


# ── 文件排除 ──────────────────────────────────

def _should_exclude(filepath: str | Path, exclude_files: list[str]) -> bool:
    """检查文件是否在排除列表中"""
    p = Path(filepath)
    fname = p.name
    for pat in exclude_files:
        if pat == fname or pat in str(p):
            return True
        # glob match
        if "*" in pat:
            import fnmatch
            if fnmatch.fnmatch(fname, pat) or fnmatch.fnmatch(str(p), pat):
                return True
    return False


# ── 核心扫描 ──────────────────────────────────

def scan_file(filepath: str | Path) -> ScanResult:
    """扫描单个文件，返回结果"""
    p = Path(filepath)
    result = ScanResult(file=str(p), language="unknown")

    if not p.exists():
        result.error = f"File not found: {p}"
        result.passed = False
        return result

    lang = _detect_language(p)
    if lang is None:
        result.language = "unknown"
        result.passed = True  # No rules = no issues
        return result
    result.language = lang

    # 加载规则
    rules = _load_rules_for_language(lang)
    if not rules:
        result.passed = True  # No rules for this language
        return result

    # 读取文件
    try:
        content = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        result.error = f"Read error: {e}"
        result.passed = False
        return result

    lines = content.split("\n")

    # 应用规则
    for rule in rules:
        pattern_str = rule.get("pattern", "")
        if not pattern_str or pattern_str == "None":
            continue

        # 检查 exclude_files
        if rule.get("exclude_files") and _should_exclude(p, rule["exclude_files"]):
            continue

        # 检查 exclude_patterns（基于内容排除）
        exclude_pats = rule.get("exclude_patterns", [])
        if exclude_pats:
            skip_rule = False
            for ep in exclude_pats:
                try:
                    if re.search(ep, content):
                        skip_rule = True
                        break
                except re.error:
                    continue
            if skip_rule:
                continue

        try:
            flags = re.IGNORECASE if rule.get("ignore_case", False) else 0
            is_multiline = rule.get("multiline", False) or ("\n" in pattern_str)

            if is_multiline:
                for match in re.finditer(pattern_str, content, flags | re.MULTILINE):
                    line_num = content[: match.start()].count("\n") + 1
                    col = match.start() - content.rfind("\n", 0, match.start()) - 1
                    result.issues.append(
                        ScanIssue(
                            file=str(p),
                            line=line_num,
                            column=max(0, col),
                            rule_id=rule.get("id", "unknown"),
                            severity=rule.get("severity", "warning"),
                            category=rule.get("category", "general"),
                            message=rule.get("message", ""),
                            fix_hint=rule.get("fix_hint", ""),
                        )
                    )
            else:
                for line_num, line in enumerate(lines, 1):
                    stripped = line.strip()
                    # 跳过注释行
                    if stripped.startswith("#") or stripped.startswith("//"):
                        continue
                    for match in re.finditer(pattern_str, line, flags):
                        result.issues.append(
                            ScanIssue(
                                file=str(p),
                                line=line_num,
                                column=match.start() + 1,
                                rule_id=rule.get("id", "unknown"),
                                severity=rule.get("severity", "warning"),
                                category=rule.get("category", "general"),
                                message=rule.get("message", ""),
                                fix_hint=rule.get("fix_hint", ""),
                            )
                        )
        except re.error:
            continue

    # Post-process: deduplicate py-missing-all (file-level check, report once)
    seen_missing_all = False
    deduped: list[ScanIssue] = []
    for issue in result.issues:
        if issue.rule_id == "py-missing-all":
            if seen_missing_all:
                continue
            seen_missing_all = True
        deduped.append(issue)
    result.issues = deduped

    result.passed = len(result.issues) == 0
    return result


def scan_files(filepaths: list[str | Path]) -> list[ScanResult]:
    """批量扫描多个文件"""
    results: list[ScanResult] = []
    for fp in filepaths:
        results.append(scan_file(fp))
    return results


# ── CLI 输出 ──────────────────────────────────

def print_results(results: list[ScanResult], verbose: bool = False) -> int:
    """打印扫描结果。返回 exit code (0=通过)"""
    total_issues = 0
    failed_files = 0

    for result in results:
        if result.error:
            print(f"❌ {result.file}: {result.error}")
            failed_files += 1
            continue
        if result.issues:
            has_errors = any(issue.severity == "error" for issue in result.issues)
            icon = "❌" if has_errors else "⚠️"
            print(f"{icon} {result.file} ({result.language}) — {len(result.issues)} issue(s)")
            for issue in result.issues:
                sev = issue.severity
                sev_icon = "🔴" if sev == "error" else ("🟡" if sev == "warning" else "ℹ️")
                print(f"   Line {issue.line}: {sev_icon} [{issue.category}] {issue.message}")
                if verbose and issue.fix_hint:
                    print(f"       💡 {issue.fix_hint}")
            total_issues += len(result.issues)
            if has_errors:
                failed_files += 1
        else:
            if verbose:
                print(f"✅ {result.file} ({result.language})")

    print(f"\nSummary: {len(results)} files, {failed_files} failed, {total_issues} issues")
    return 1 if failed_files > 0 else 0
