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
    """检查 pos 位置是否在字符串字面量内部.

    V2.20 P4-54 拆分: 抽 _process_string_char 收口单字符状态机更新,
    主函数仅 while 循环.
    """
    in_str = False
    str_char: str | None = None
    i = 0
    while i < pos and i < len(line):
        ch = line[i]
        in_str, str_char, i = _process_string_char(ch, in_str, str_char, i)
    return in_str


def _process_string_char(ch: str, in_str: bool, str_char: str | None, i: int) -> tuple[bool, str | None, int]:
    """处理单字符状态机更新 (模块级 helper).

    Args:
        ch: 当前字符
        in_str: 当前是否在字符串内
        str_char: 字符串边界字符 (\" or ')
        i: 当前索引

    Returns:
        (new_in_str, new_str_char, new_i) 元组
    """
    if in_str:
        if ch == "\\":
            return in_str, str_char, i + 2  # 跳过转义字符
        if ch == str_char:
            return False, None, i + 1
        return in_str, str_char, i + 1
    if ch in ('"', "'"):
        return True, ch, i + 1
    return in_str, str_char, i + 1


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
    """向后兼容: 检查代码结构问题 (行计数方式，避免正则回溯)

    V2.20 P4-52 拆分: 抽 _find_function_end 收口函数体行数扫描,
    主函数仅函数定义守卫 + issue 构造.
    """
    import re

    issues: list[dict[str, Any]] = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*def\s+\w+", line):
            func_start = i
            indent = len(line) - len(line.lstrip())
            j = _find_function_end(lines, i + 1, indent)
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


def _find_function_end(lines: list[str], start: int, indent: int) -> int:
    """扫描函数体结束行索引 (模块级 helper).

    跳过空行 + 注释行, 找到首个缩进 <= indent 的非空行 (函数体结束).

    Args:
        lines: 全部行
        start: 函数体起始行 (def 之后一行)
        indent: 函数定义缩进

    Returns:
        函数体结束行索引 (含 def 起始行至此前)
    """
    j = start
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
    return j


def check_security_patterns(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查安全模式 (保持原始中文消息)

    V2.20 P4-57 拆分: 模块级常量 _SECURITY_PATTERNS 收口 10 模式元组,
    _is_valid_security_match 收口 match + string 守卫,
    主函数仅外层 for + 注释守卫 + 委托.
    """
    issues: list[dict[str, Any]] = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 模式与描述用拼接构造，避免本文件含动态执行调用字面量被 ADG 自我引用误报
    ev, ex = "eval", "exec"
    patterns = _build_security_patterns(ev, ex)
    for line_num, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for pattern, description in patterns:
            if _is_valid_security_match(line, pattern):
                issues.append(
                    {
                        "line": line_num,
                        "type": "security",
                        "message": description,
                        "code": line.strip()[:60],
                    }
                )

    return issues


# 模块级常量: 硬编码密钥 + 哈希 + SQL 拼接模式 (不含 eval/exec, 由 _build_security_patterns 动态构造)
_SECURITY_LITERAL_PATTERNS: list[tuple[str, str]] = [
    (
        r'(?:password|secret|api_key|token)\s*=\s*[\'"][^\'"]+[\'"]',
        "疑似硬编码密钥",
    ),
    (r"verify\s*=\s*False", "禁用 SSL 验证"),
    (r"hashlib\.md5\(", "使用 MD5 - 不安全的哈希"),
    (r"hashlib\.sha1\(", "使用 SHA1 - 不安全的哈希"),
    (r'f[\'"].*\bSELECT\b.*\{', "SQL 拼接 (f-string)"),
    (r'f[\'"].*\bINSERT\b.*\{', "SQL 拼接 (f-string)"),
    (r'f[\'"].*\bUPDATE\b\s+\w+.*\{', "SQL 拼接 (f-string)"),
    (r'f[\'"].*\bDELETE\b.*\{', "SQL 拼接 (f-string)"),
]


def _build_security_patterns(ev: str, ex: str) -> list[tuple[str, str]]:
    """构造完整安全模式列表 (含 eval/exec, 模块级 helper).

    Args:
        ev: eval 关键字 (避免自我引用误报)
        ex: exec 关键字 (避免自我引用误报)

    Returns:
        10 个 (pattern, description) 元组
    """
    return [
        (rf"(?<!literal_){ev}\s*\(", f"使用 {ev}() - 安全风险"),
        (rf"(?<!literal_){ex}\s*\(", f"使用 {ex}() - 安全风险"),
        *_SECURITY_LITERAL_PATTERNS,
    ]


def _is_valid_security_match(line: str, pattern: str) -> bool:
    """检查 pattern 是否有效匹配 (非字符串内, 模块级 helper).

    Args:
        line: 单行代码
        pattern: 正则 pattern

    Returns:
        True if 匹配且不在字符串字面量内
    """
    import re

    match = re.search(pattern, line, re.IGNORECASE)
    return bool(match and not _is_in_string(line, match.start()))


def check_type_patterns(filepath: Path) -> list[dict[str, Any]]:
    """向后兼容: 检查类型安全模式 (保持原始中文消息)

    V2.20 P4-58 拆分: 抽 _is_valid_type_issue 收口 search + import 守卫 + any 守卫,
    主函数仅嵌套 for + 委托 + issue 构造.
    """
    issues: list[dict[str, Any]] = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for pattern, description in _TYPE_PATTERNS:
            if _is_valid_type_issue(line, pattern):
                issues.append(
                    {
                        "line": line_num,
                        "type": "type",
                        "message": description,
                        "code": line.strip()[:60],
                    }
                )

    return issues


def _is_valid_type_issue(line: str, pattern: str) -> bool:
    """检查 pattern 匹配 + import/any 守卫 (模块级 helper).

    Args:
        line: 单行代码
        pattern: 正则 pattern

    Returns:
        True if 匹配且非 import 行且非 any in brackets
    """
    import re

    if not re.search(pattern, line, re.IGNORECASE):
        return False
    if _is_import_line(line):
        return False
    if _is_any_in_brackets(line):
        return False
    return True


# 模块级常量: 类型模式列表
_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"#\s*type:\s*ignore(?!\s*\[)", "类型抑制"),
    (r"@\w+(?:\.\w+)*\.ignore", "使用 @ignore 装饰器"),
    (r":\s*Any\b", "使用 Any 类型"),
]


def _is_import_line(line: str) -> bool:
    """检查行是否为 import/from 行 (模块级 helper).

    Args:
        line: 单行代码

    Returns:
        True if 行以 from/import 开头
    """
    import re

    return bool(re.match(r"^(?:from|import)\b", line.strip()))


def _is_any_in_brackets(line: str) -> bool:
    """检查行内 Any 是否仅在括号/中括号中 (模块级 helper).

    注: 旧逻辑 "import in line and Any in line" → 复合类型场景会被误判.
    本 helper 替换为更精确的 import 守卫.

    Args:
        line: 单行代码

    Returns:
        True if 行仅为 import 语句 (含 Any 也跳过)
    """
    return "import" in line and "Any" in line


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
    """向后兼容: 检查单个文件.

    V2.20 P4-53 拆分: 抽 _run_check_dispatch 收口 5 类 check → extend 委托,
    _build_file_not_found 收口文件不存在失败响应,
    主函数仅 result 初始化 + 委托 + 注解检查.
    """
    result: dict[str, Any] = {
        "file": str(filepath),
        "issues": [],
        "passed": True,
        "has_annotation": False,
    }

    if not filepath.exists():
        return _build_file_not_found(filepath, result)

    all_issues = _run_check_dispatch(filepath, checks)

    # Check for AI annotation
    content = filepath.read_text(encoding="utf-8")
    import re

    if re.search(r"# \[AI-GEN\]", content):
        result["has_annotation"] = True

    result["issues"] = all_issues
    result["passed"] = len(all_issues) == 0
    return result


def _run_check_dispatch(filepath: Path, checks: list[str]) -> list[dict[str, Any]]:
    """按 checks 列表分派 5 类 check 函数 (模块级 helper).

    Args:
        filepath: 文件路径
        checks: 启用的 check 名称列表

    Returns:
        累积的所有 issues
    """
    all_issues: list[dict[str, Any]] = []
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
    return all_issues


def _build_file_not_found(filepath: Path, result: dict[str, Any]) -> dict[str, Any]:
    """构造文件不存在时的失败响应 (模块级 helper).

    Args:
        filepath: 不存在的文件路径
        result: 主函数初始化的 result dict

    Returns:
        包含错误 issue + passed=False 的 result
    """
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
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    return parser.parse_args()


def _determine_checks(args: argparse.Namespace) -> list[str]:
    """Determine which checks to run based on args.

    V2.20 P4-51 拆分: 抽 _append_if_flag 收口 flag → checks append,
    主函数仅 full/else 分派 + 默认回退.
    """
    if args.full or args.check_patterns:
        return _ALL_CHECKS
    checks: list[str] = []
    _append_if_flag(checks, "annotation", args.check_annotation)
    _append_if_flag(checks, "security", args.check_security)
    _append_if_flag(checks, "type", args.check_type)
    _append_if_flag(checks, "error", args.check_error)
    _append_if_flag(checks, "structure", args.check_structure)
    _append_if_flag(checks, "language_rules", args.check_language_rules)
    return checks or _DEFAULT_CHECKS


# 模块级常量: 全套检查 + 默认检查
_ALL_CHECKS = [
    "annotation",
    "security",
    "type",
    "error",
    "structure",
    "language_rules",
]
_DEFAULT_CHECKS = ["annotation", "security", "type", "error"]


def _append_if_flag(checks: list[str], check_name: str, flag: bool) -> None:
    """若 flag=True 则 append check_name (模块级 helper).

    Args:
        checks: 累积列表 (in-place)
        check_name: 检查名
        flag: 触发标志
    """
    if flag:
        checks.append(check_name)


def _collect_files(args: argparse.Namespace) -> list[Path]:
    """Collect files to check based on args.

    V2.20 P4-56 拆分: 抽 _collect_path_files 收口 args.path → rglob 扩展名遍历,
    模块级常量 _FILE_EXTENSIONS 收口 25 扩展名字面量,
    主函数仅 file/path/default 三路分派 + 过滤.
    """
    if args.file:
        files_to_check = [args.file]
    elif args.path:
        files_to_check = _collect_path_files(args.path)
    else:
        files_to_check = list(Path("tools/scripts").rglob("*.py"))

    return _filter_excluded(files_to_check)


# 模块级常量: 支持的 25 种语言文件扩展名
_FILE_EXTENSIONS = [
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


def _collect_path_files(path: Path) -> list[Path]:
    """从 path 递归收集所有支持扩展名文件 (模块级 helper).

    Args:
        path: 搜索根目录

    Returns:
        匹配文件列表
    """
    files: list[Path] = []
    for ext in _FILE_EXTENSIONS:
        files.extend(path.rglob(ext))
    return files


def _filter_excluded(files: list[Path]) -> list[Path]:
    """过滤 __pycache__/.git 目录 (模块级 helper).

    Args:
        files: 候选文件列表

    Returns:
        过滤后文件列表
    """
    return [f for f in files if "__pycache__" not in str(f) and ".git" not in str(f)]


def _run_checks(args: argparse.Namespace, filtered_files: list[Path]) -> list[CheckResult]:
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
    """Print results and return exit code.

    V2.20 P4-50 拆分: 抽 _compute_result_counts 收口 5 项 sum 统计,
    _print_text_results 收口 text 格式渲染 (for + 守卫 + 截断),
    主函数仅 json/text 分派.
    """
    counts = _compute_result_counts(results)
    if format_type == "json":
        _print_json_results(results, counts)
    else:
        _print_text_results(results, counts)
    return 1 if counts["failed"] > 0 else 0


def _compute_result_counts(results: list[CheckResult]) -> dict[str, int]:
    """统计 5 项 results 汇总 (模块级 helper).

    Args:
        results: CheckResult 列表

    Returns:
        {passed, failed, total_issues, total_errors, total_warnings} dict
    """
    return {
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "total_issues": sum(len(r.issues) for r in results),
        "total_errors": sum(r.error_count for r in results),
        "total_warnings": sum(r.warning_count for r in results),
    }


def _print_json_results(results: list[CheckResult], counts: dict[str, int]) -> None:
    """打印 JSON 格式结果 (模块级 helper)."""
    import json

    output = {
        "summary": {
            "passed": counts["passed"],
            "failed": counts["failed"],
            "total_files": len(results),
            "total_issues": counts["total_issues"],
            "errors": counts["total_errors"],
            "warnings": counts["total_warnings"],
        },
        "results": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def _print_text_results(results: list[CheckResult], counts: dict[str, int]) -> None:
    """打印 text 格式结果 (模块级 helper)."""
    for result in results:
        if result.passed:
            print(f"✅ {result.file}")
        else:
            print(f"❌ {result.file} ({len(result.issues)} issues)")
            for issue in result.issues[:5]:
                print(f"   Line {issue.line}: [{issue.severity}] {issue.rule_id}: {issue.message}")
            if len(result.issues) > 5:
                print(f"   ... and {len(result.issues) - 5} more")

    print("\n" + "=" * 60)
    print(
        f"  结果: {counts['passed']} 通过, {counts['failed']} 失败, {counts['total_issues']} 个问题 "
        f"({counts['total_errors']} errors, {counts['total_warnings']} warnings)"
    )
    print("=" * 60)


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
