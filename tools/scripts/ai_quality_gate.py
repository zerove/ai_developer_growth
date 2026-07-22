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
    (r"@\w+\.ignore", "使用 @ignore 装饰器"),
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
                issues.append({
                    "line": line_num,
                    "type": "security",
                    "message": description,
                    "code": line.strip()[:60],
                })

    return issues


def check_type_patterns(filepath: Path) -> list[dict]:
    """检查类型安全反模式"""
    issues = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for pattern, description in TYPE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append({
                    "line": line_num,
                    "type": "type",
                    "message": description,
                    "code": line.strip()[:60],
                })

    return issues


def check_error_patterns(filepath: Path) -> list[dict]:
    """检查错误处理反模式"""
    issues = []
    content = filepath.read_text(encoding="utf-8")

    for pattern, description in ERROR_PATTERNS:
        for match in re.finditer(pattern, content, re.MULTILINE):
            line_num = content[:match.start()].count("\n") + 1
            issues.append({
                "line": line_num,
                "type": "error",
                "message": description,
                "code": match.group()[:60],
            })

    return issues


def check_structure_patterns(filepath: Path) -> list[dict]:
    """检查代码结构问题"""
    issues = []
    content = filepath.read_text(encoding="utf-8")

    for pattern, description in STRUCTURE_PATTERNS:
        for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
            line_num = content[:match.start()].count("\n") + 1
            issues.append({
                "line": line_num,
                "type": "structure",
                "message": description,
                "code": "...",
            })

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
                issues.append({
                    "line": 1,
                    "type": "annotation",
                    "message": "检测到 AI 生成代码但缺少 [AI-GEN] 标注",
                    "code": "...",
                })
                break

    return issues


def check_file(filepath: Path, checks: list[str]) -> dict:
    """检查单个文件"""
    result = {
        "file": str(filepath),
        "issues": [],
        "passed": True,
    }

    if not filepath.exists():
        result["issues"].append({
            "line": 0,
            "type": "error",
            "message": f"文件不存在: {filepath}",
            "code": "",
        })
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


def main():
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
    args = parser.parse_args()

    # 确定检查项
    checks = []
    if args.full or args.check_patterns:
        checks = ["annotation", "security", "type", "error", "structure"]
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
        files_to_check = list(args.path.rglob("*.py"))
    else:
        files_to_check = list(Path("tools/scripts").rglob("*.py"))

    passed = 0
    failed = 0
    total_issues = 0

    for filepath in sorted(files_to_check):
        if "__pycache__" in str(filepath):
            continue

        result = check_file(filepath, checks)

        if result["passed"]:
            print(f"✅ {filepath.name}")
            passed += 1
        else:
            print(f"❌ {filepath.name} ({len(result['issues'])} issues)")
            for issue in result["issues"][:5]:  # 最多显示 5 个
                print(f"   Line {issue['line']}: [{issue['type']}] {issue['message']}")
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
