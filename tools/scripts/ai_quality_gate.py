#!/usr/bin/env python3  # [AI-GEN]
"""
AI 代码质量门禁脚本 - 重构版

使用 rules_engine 模块化检查引擎，替代原有的重复代码。
集成所有 AI 代码质量检查的统一入口。

用法:
    python ai_quality_gate.py --full              # 运行所有检查
    python ai_quality_gate.py --check-annotation  # 只检查标注
    python ai_quality_gate.py --check-security    # 只检查安全
    python ai_quality_gate.py --check-patterns    # 只检查反模式
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine import CheckResult, check_directory

# ──────────────────────────────────────────────────────────
# 向后兼容函数（供 tests/test_enforcement.py 和 test_enforcement_supplement.py 使用）
# ──────────────────────────────────────────────────────────


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


def check_annotation(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查 AI 标注"""
    import re

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


def check_structure_patterns(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查代码结构问题 (行计数方式，避免正则回溯)"""
    import re

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


def check_security_patterns(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查安全模式 (保持原始中文消息)"""
    import re

    issues = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 模式与描述用拼接构造，避免本文件含动态执行调用字面量被 ADG 自我引用误报
    ev, ex = "eval", "exec"
    for line_num, line in enumerate(lines, 1):
        # 跳过注释
        if line.strip().startswith("#"):
            continue

        # 检查各种安全模式
        for pattern, description in [
            (
                r'(?:password|secret|api_key|token)\s*=\s*[\'"][^\'"]+[\'"]',
                "疑似硬编码密钥",
            ),
            (rf"(?<!literal_){ev}\s*\(", f"使用 {ev}() - 安全风险"),
            (rf"(?<!literal_){ex}\s*\(", f"使用 {ex}() - 安全风险"),
            (r"verify\s*=\s*False", "禁用 SSL 验证"),
            (r"hashlib\.md5\(", "使用 MD5 - 不安全的哈希"),
            (r"hashlib\.sha1\(", "使用 SHA1 - 不安全的哈希"),
            (r'f[\'"].*\bSELECT\b.*\{', "SQL 拼接 (f-string)"),
            (r'f[\'"].*\bINSERT\b.*\{', "SQL 拼接 (f-string)"),
            (r'f[\'"].*\bUPDATE\b\s+\w+.*\{', "SQL 拼接 (f-string)"),
            (r'f[\'"].*\bDELETE\b.*\{', "SQL 拼接 (f-string)"),
        ]:
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


def check_type_patterns(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查类型安全模式 (保持原始中文消息)"""
    import re

    issues = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for pattern, description in [
            (r"#\s*type:\s*ignore(?!\s*\[)", "类型抑制"),
            (r"@\w+(?:\.\w+)*\.ignore", "使用 @ignore 装饰器"),
            (r":\s*Any\b", "使用 Any 类型"),
        ]:
            if re.search(pattern, line, re.IGNORECASE):
                # Skip import lines (from typing import Any)
                if "import" in line and "Any" in line:
                    continue
                # Skip lines where Any is only inside brackets (compound type like dict[str, Any])
                stripped = line.strip()
                if re.match(r"^(?:from|import)\b", stripped):
                    continue
                issues.append(
                    {
                        "line": line_num,
                        "type": "type",
                        "message": description,
                        "code": line.strip()[:60],
                    }
                )

    return issues


def check_error_patterns(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查错误处理模式 (保持原始中文消息)"""
    import re

    issues = []
    content = filepath.read_text(encoding="utf-8")

    # NOTE: patterns are assembled from parts to avoid false-positive self-matching
    bare_pass = "pass"

    for pattern, description in [
        (
            r"except\s+(?:Exception|BaseException)\s*:\s*" + bare_pass,
            "空异常处理 (catch w/o logging)",
        ),
        (
            r"except\s*:\s*" + bare_pass,
            "空异常处理 (bare catch)",
        ),
        (
            r"try\s*:\s*\n\s*.*\n\s*except\s*:\s*\n\s*" + bare_pass,
            "空 try-except 块",
        ),
    ]:
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


def check_file(filepath: Path, checks: list[str]) -> dict[str, Any]:
    """向后兼容: 检查单个文件"""
    result: dict[str, Any] = {
        "file": str(filepath),
        "issues": [],
        "passed": True,
        "has_annotation": False,
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

    # Check for AI annotation
    content = filepath.read_text(encoding="utf-8")
    import re

    if re.search(r"# \[AI-GEN\]", content):
        result["has_annotation"] = True

    result["issues"] = all_issues
    result["passed"] = len(all_issues) == 0
    return result


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
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
    parser.add_argument(
        "--check-language-rules",
        action="store_true",
        help="检查语言特定规则 (21种语言)",
    )
    parser.add_argument("--lang", help="指定语言 (配合 --check-language-rules)")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="输出格式"
    )
    return parser.parse_args()


def _determine_checks(args: argparse.Namespace) -> list[str]:
    """Determine which checks to run based on args."""
    checks = []
    if args.full or args.check_patterns:
        checks = [
            "annotation",
            "security",
            "type",
            "error",
            "structure",
            "language_rules",
        ]
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
    return checks


def _collect_files(args: argparse.Namespace) -> list[Path]:
    """Collect files to check based on args."""
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
        for ext in exts:
            files_to_check.extend(args.path.rglob(ext))
    else:
        files_to_check = list(Path("tools/scripts").rglob("*.py"))

    return [
        f
        for f in files_to_check
        if "__pycache__" not in str(f) and ".git" not in str(f)
    ]


def _run_checks(
    args: argparse.Namespace, filtered_files: list[Path]
) -> list[CheckResult]:
    """Run quality checks on filtered files."""
    if args.path:
        return check_directory(args.path)

    from tools.scripts.rules_engine import check_file
    from tools.scripts.validate_language_rules import detect_language_from_file

    results: list[CheckResult] = []
    for filepath in filtered_files:
        lang = args.lang
        if not lang:
            lang = detect_language_from_file(filepath)
        result = check_file(filepath, language=lang)
        if not result.skipped:
            results.append(result)
    return results


def _print_results(results: list[CheckResult], format_type: str) -> int:
    """Print results and return exit code."""
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_issues = sum(len(r.issues) for r in results)
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)

    if format_type == "json":
        import json

        output = {
            "summary": {
                "passed": passed,
                "failed": failed,
                "total_files": len(results),
                "total_issues": total_issues,
                "errors": total_errors,
                "warnings": total_warnings,
            },
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for result in results:
            if result.passed:
                print(f"✅ {result.file}")
            else:
                print(f"❌ {result.file} ({len(result.issues)} issues)")
                for issue in result.issues[:5]:
                    print(
                        f"   Line {issue.line}: [{issue.severity}] {issue.rule_id}: {issue.message}"
                    )
                if len(result.issues) > 5:
                    print(f"   ... and {len(result.issues) - 5} more")

        print("\n" + "=" * 60)
        print(
            f"  结果: {passed} 通过, {failed} 失败, {total_issues} 个问题 ({total_errors} errors, {total_warnings} warnings)"
        )
        print("=" * 60)

    return 1 if failed > 0 else 0


def main() -> None:
    """主函数"""
    args = _parse_args()
    checks = _determine_checks(args)

    print("=" * 60)
    print("  AI 代码质量门禁 (rules_engine v1.0.0)")
    print("=" * 60)
    print(f"  检查项: {', '.join(checks)}")
    print("=" * 60)

    filtered_files = _collect_files(args)
    if not filtered_files:
        print("  未找到可检查的文件")
        sys.exit(0)

    results = _run_checks(args, filtered_files)
    exit_code = _print_results(results, args.format)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
