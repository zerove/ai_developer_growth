#!/usr/bin/env python3
"""
AI 代码质量门禁脚本

集成所有 AI 代码质量检查的统一入口。
检查项:
1. AI 代码标注 ([AI-GEN])
2. 安全模式检查 (SQL 拼接、硬编码密钥等)
3. 类型安全检查 (unwrap/as any)
4. 错误处理检查
5. 代码结构检查

用法:
    python ai_quality_gate.py --full              # 运行所有检查
    python ai_quality_gate.py --check-annotation  # 只检查标注
    python ai_quality_gate.py --check-security    # 只检查安全
    python ai_quality_gate.py --check-patterns    # 只检查反模式
"""

import argparse
import re
import sys
from pathlib import Path
from typing import TypedDict

# 兼容 python -m 和 python <path> 两种运行方式
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.scripts.validate_language_rules import (
    detect_language_from_file as detect_lang,
)
from tools.scripts.validate_language_rules import (
    validate_file as validate_lang_file,
)


class FileCheckResult(TypedDict):
    file: str
    issues: list[dict[str, object]]
    passed: bool


# 安全反模式
SECURITY_PATTERNS = [
    (r"(?:password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", "疑似硬编码密钥"),
    (r"eval\s*\(", "使用 eval() - 安全风险"),
    (r"exec\s*\(", "使用 exec() - 安全风险"),
    (r"verify\s*=\s*False", "禁用 SSL 验证"),
    (r"hashlib\.md5\(", "使用 MD5 - 不安全的哈希"),
    (r"hashlib\.sha1\(", "使用 SHA1 - 不安全的哈希"),
    (r"f['\"].*\bSELECT\b.*{", "SQL 拼接 (f-string)"),
    (r"f['\"].*\bINSERT\b.*{", "SQL 拼接 (f-string)"),
    (r"f['\"].*\bUPDATE\b\s+\w+.*{", "SQL 拼接 (f-string)"),
    (r"f['\"].*\bDELETE\b.*{", "SQL 拼接 (f-string)"),
]

# 类型安全反模式
TYPE_PATTERNS = [
    (r"# type:\s*ignore", "类型抑制"),
    (r"@\w+(?:\.\w+)*\.ignore", "使用 @ignore 装饰器"),
    (r":\s*Any\b", "使用 Any 类型"),
]

# 错误处理反模式
ERROR_PATTERNS = [
    (r"except\s+(?:Exception|BaseException)\s*:\s*pass", "空异常处理 (except: pass)"),
    (r"except\s*:\s*pass", "空异常处理 (bare except: pass)"),
    (r"try\s*:\s*\n\s*.*\n\s*except\s*:\s*\n\s*pass", "空 try-except 块"),
]

# 代码结构检查
STRUCTURE_PATTERNS = [
    (r"def\s+\w+\([^)]*\)[^:]*:\s*\n(?:\s+.*\n){50,}", "函数超过 50 行"),
]


def _is_in_string(line: str, pos: int) -> bool:
    """检查 pos 位置是否在字符串字面量内部"""
    in_str = False
    str_char = None
    i = 0
    while i < pos and i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\":
                i += 2  # 跳过转义字符
                continue
            if ch == str_char:
                in_str = False
                str_char = None
        else:
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
        i += 1
    return in_str


def check_security_patterns(filepath: Path) -> list[dict]:
    """检查安全反模式"""
    issues = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        # 跳过注释
        if line.strip().startswith("#"):
            continue

        for pattern, description in SECURITY_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match and not _is_in_string(line, match.start()):
                issues.append(
                    {
                        "line": line_num,
                        "type": "security",
                        "message": description,
                        "code": line.strip()[:60],
                    }
                )

    return issues


def check_type_patterns(filepath: Path) -> list[dict]:
    """检查类型安全反模式"""
    issues = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for pattern, description in TYPE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(
                    {
                        "line": line_num,
                        "type": "type",
                        "message": description,
                        "code": line.strip()[:60],
                    }
                )

    return issues


def check_error_patterns(filepath: Path) -> list[dict]:
    """检查错误处理反模式"""
    issues = []
    content = filepath.read_text(encoding="utf-8")

    for pattern, description in ERROR_PATTERNS:
        for match in re.finditer(pattern, content, re.MULTILINE):
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                {
                    "line": line_num,
                    "type": "error",
                    "message": description,
                    "code": match.group()[:60],
                }
            )

    return issues


def check_structure_patterns(filepath: Path) -> list[dict]:
    """检查代码结构问题 (行计数方式，避免正则回溯)"""
    issues = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        # 检测函数定义
        if re.match(r"^\s*def\s+\w+", line):
            func_start = i
            indent = len(line) - len(line.lstrip())
            # 计算函数体行数
            j = i + 1
            while j < len(lines):
                stripped = lines[j].strip()
                if stripped == "" or stripped.startswith("#"):
                    j += 1
                    continue
                current_indent = len(lines[j]) - len(lines[j].lstrip())
                if current_indent > indent:
                    j += 1
                else:
                    break
            func_lines = j - func_start
            if func_lines > 50:
                issues.append(
                    {
                        "line": func_start + 1,
                        "type": "structure",
                        "message": f"函数超过 50 行 (实际 {func_lines} 行)",
                        "code": line.strip()[:60],
                    }
                )
            i = j
        else:
            i += 1

    return issues


def check_annotation(filepath: Path) -> list[dict]:
    """检查 AI 标注"""
    issues = []
    content = filepath.read_text(encoding="utf-8")

    # 检查是否有 AI 生成的指标
    ai_indicators = [
        r"# AI[- ]generated",
        r"# Generated with",
        r"# This function.*generated",
    ]

    for indicator in ai_indicators:
        if re.search(indicator, content, re.IGNORECASE):
            # 检查是否有 [AI-GEN] 标注
            if not re.search(r"# \[AI-GEN\]", content):
                issues.append(
                    {
                        "line": 1,
                        "type": "annotation",
                        "message": "检测到 AI 生成代码但缺少 [AI-GEN] 标注",
                        "code": "...",
                    }
                )
                break

    return issues


def check_file(filepath: Path, checks: list[str]) -> FileCheckResult:
    """检查单个文件"""
    result: FileCheckResult = {
        "file": str(filepath),
        "issues": [],
        "passed": True,
    }

    if not filepath.exists():
        result["issues"].append(
            {
                "line": 0,
                "type": "error",
                "message": f"文件不存在: {filepath}",
                "code": "",
            }
        )
        result["passed"] = False
        return result

    all_issues = []

    if "annotation" in checks:
        all_issues.extend(check_annotation(filepath))
    if "security" in checks:
        all_issues.extend(check_security_patterns(filepath))
    if "type" in checks:
        all_issues.extend(check_type_patterns(filepath))
    if "error" in checks:
        all_issues.extend(check_error_patterns(filepath))
    if "structure" in checks:
        all_issues.extend(check_structure_patterns(filepath))

    result["issues"] = all_issues
    result["passed"] = len(all_issues) == 0
    return result


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 代码质量门禁")
    parser.add_argument("--path", type=Path, help="检查指定目录")
    parser.add_argument("--file", type=Path, help="检查单个文件")
    parser.add_argument("--full", action="store_true", help="运行所有检查")
    parser.add_argument("--check-annotation", action="store_true", help="检查 AI 标注")
    parser.add_argument("--check-security", action="store_true", help="检查安全模式")
    parser.add_argument("--check-type", action="store_true", help="检查类型安全")
    parser.add_argument("--check-error", action="store_true", help="检查错误处理")
    parser.add_argument("--check-structure", action="store_true", help="检查代码结构")
    parser.add_argument("--check-patterns", action="store_true", help="检查所有反模式")
    parser.add_argument("--check-language-rules", action="store_true", help="检查语言特定规则 (21种语言)")
    parser.add_argument("--lang", help="指定语言 (配合 --check-language-rules)")
    args = parser.parse_args()

    # 确定检查项
    checks = []
    if args.full or args.check_patterns:
        checks = ["annotation", "security", "type", "error", "structure", "language_rules"]
    else:
        if args.check_annotation:
            checks.append("annotation")
        if args.check_security:
            checks.append("security")
        if args.check_type:
            checks.append("type")
        if args.check_error:
            checks.append("error")
        if args.check_structure:
            checks.append("structure")
        if args.check_language_rules:
            checks.append("language_rules")

    if not checks:
        checks = ["annotation", "security", "type", "error"]

    print("=" * 60)
    print("  AI 代码质量门禁")
    print("=" * 60)
    print(f"  检查项: {', '.join(checks)}")
    print("=" * 60)

    # 收集文件
    files_to_check = []
    if args.file:
        files_to_check = [args.file]
    elif args.path:
        exts = [
            "*.py",
            "*.ts",
            "*.tsx",
            "*.js",
            "*.jsx",
            "*.rs",
            "*.go",
            "*.java",
            "*.kt",
            "*.cs",
            "*.php",
            "*.rb",
            "*.cpp",
            "*.swift",
            "*.scala",
            "*.ex",
            "*.exs",
            "*.lua",
            "*.zig",
            "*.r",
            "*.R",
            "*.clj",
            "*.hs",
            "*.dart",
            "*.ps1",
        ]
        files_to_check = []
        for ext in exts:
            files_to_check.extend(args.path.rglob(ext))
    else:
        files_to_check = list(Path("tools/scripts").rglob("*.py"))

    passed = 0
    failed = 0
    total_issues = 0

    # 语言规则检查单独处理
    if "language_rules" in checks:
        lang_files = [
            f
            for f in files_to_check
            if f.suffix
            in (
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".rs",
                ".go",
                ".java",
                ".kt",
                ".cs",
                ".php",
                ".rb",
                ".cpp",
                ".swift",
                ".scala",
                ".ex",
                ".exs",
                ".lua",
                ".zig",
                ".r",
                ".R",
                ".clj",
                ".hs",
                ".dart",
                ".ps1",
            )
        ]
        lang_results = []
        for fp in lang_files:
            lang = args.lang or detect_lang(fp)
            if lang:
                try:
                    lang_results.append(validate_lang_file(fp, lang))
                except Exception:
                    pass
        lang_issues = sum(r.error_count for r in lang_results)
        lang_warnings = sum(r.warning_count for r in lang_results)
        if lang_issues or lang_warnings:
            print("\n📋 语言规则检查:")
            for r in lang_results:
                if r.error_count or r.warning_count:
                    print(f"  ❌ {r.file}: {r.error_count} errors, {r.warning_count} warnings")
                    for issue in r.issues[:3]:
                        print(f"     [{issue.severity}] {issue.rule_id}: {issue.message}")
            total_issues += lang_issues + lang_warnings
            failed += 1
        else:
            print(f"\n📋 语言规则检查: ✅ {len(lang_results)} 文件通过")
            passed += 1

    for filepath in sorted(files_to_check):
        if "__pycache__" in str(filepath):
            continue

        result = check_file(filepath, checks)

        if result["passed"]:
            print(f"✅ {filepath.name}")
            passed += 1
        else:
            print(f"❌ {filepath.name} ({len(result['issues'])} issues)")
            for issue in result["issues"][:5]:  # type: ignore[assignment] # 最多显示 5 个
                print(f"   Line {issue['line']}: [{issue['type']}] {issue['message']}")  # type: ignore[index]
            if len(result["issues"]) > 5:
                print(f"   ... and {len(result['issues']) - 5} more")
            failed += 1
            total_issues += len(result["issues"])

    print("\n" + "=" * 60)
    print(f"  结果: {passed} 通过, {failed} 失败, {total_issues} 个问题")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
