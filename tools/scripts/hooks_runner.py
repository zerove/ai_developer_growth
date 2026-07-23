#!/usr/bin/env python3
"""
统一 Hook 运行器

统一了 jcode hook 系统和 AI Quality Gate / Governance Auditor 的检查逻辑。
可被 CI/CD workflow 复用，也可被 pre-commit hook 调用。

用法:
    python hooks_runner.py lint
    python hooks_runner.py format
    python hooks_runner.py typecheck
    python hooks_runner.py test
    python hooks_runner.py security
    python hooks_runner.py language-rules [--path PATH] [--lang LANG]
    python hooks_runner.py quality-gate [--path PATH] [--full] [--check-security] ...
    python hooks_runner.py governance-audit [--full] [--validate-docs] [--check-ai-sdlc] [--audit-hallucination]
    python hooks_runner.py full
"""

import argparse
import subprocess
import sys
from pathlib import Path

# 兼容 python -m 和 python <path> 两种运行方式
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.scripts.ai_quality_gate import (
    check_file,
)
from tools.scripts.validate_language_rules import (
    detect_language_from_file,
    validate_directory,
    validate_file,
)

# =============================================================================
# 基础检查函数
# =============================================================================


def run_lint() -> tuple[bool, str]:
    """运行 ruff lint 检查"""

    result = subprocess.run(
        ["ruff", "check", "."],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_format_check() -> tuple[bool, str]:
    """运行 ruff format 检查"""

    result = subprocess.run(
        ["ruff", "format", "--check", "."],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_typecheck() -> tuple[bool, str]:
    """运行 mypy 类型检查"""

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "tools/scripts/", "--ignore-missing-imports"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_tests() -> tuple[bool, str]:
    """运行 pytest 测试套件"""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--cov=tools/scripts",
            "--cov-report=term-missing",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_security() -> tuple[bool, str]:
    """运行安全扫描"""

    results = []

    # bandit
    result1 = subprocess.run(
        ["bandit", "-r", "tools/scripts/", "-f", "json", "-o", "bandit-report.json", "-ll"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    results.append(("bandit", result1.returncode == 0, result1.stdout + result1.stderr))

    # pip-audit
    result2 = subprocess.run(
        ["pip-audit", "--desc"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    results.append(("pip-audit", result2.returncode == 0, result2.stdout + result2.stderr))

    all_passed = all(r[1] for r in results)
    output = "\n".join(f"=== {r[0]} ===\n{r[2]}" for r in results)
    return all_passed, output


def run_language_rules(path: Path, lang: str | None = None) -> tuple[bool, str]:
    """运行语言特定规则检查"""
    if path.is_file():
        language = lang or detect_language_from_file(path)
        if not language:
            return False, f"Cannot detect language for {path}"
        result = validate_file(path, language)
        return result.passed, str(result.to_dict())
    else:
        results = validate_directory(path)
        passed = all(r.passed for r in results)
        output = "\n".join(f"{r.file}: {'PASS' if r.passed else 'FAIL'} ({len(r.issues)} issues)" for r in results)
        return passed, output


def run_quality_gate(
    path: Path,
    full: bool = False,
    check_annotation: bool = False,
    check_security: bool = False,
    check_type: bool = False,
    check_error: bool = False,
    check_structure: bool = False,
    check_patterns: bool = False,
    format: str = "text",
) -> tuple[bool, str]:
    """运行 AI Quality Gate 检查"""
    checks = []
    if full or check_patterns:
        checks = ["annotation", "security", "type", "error", "structure", "language_rules"]
    else:
        if check_annotation:
            checks.append("annotation")
        if check_security:
            checks.append("security")
        if check_type:
            checks.append("type")
        if check_error:
            checks.append("error")
        if check_structure:
            checks.append("structure")

    if not checks:
        checks = ["annotation", "security", "type", "error"]

    files_to_check = []
    if path.is_file():
        files_to_check = [path]
    else:
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
            files_to_check.extend(path.rglob(ext))

    filtered_files = [f for f in files_to_check if "__pycache__" not in str(f) and ".git" not in str(f)]

    if not filtered_files:
        return True, "No files to check"

    all_results = []
    for filepath in filtered_files:
        lang = detect_language_from_file(filepath)
        if not lang:
            continue
        result = check_file(filepath, checks)
        all_results.append((filepath, result))

    passed_count = sum(1 for _, r in all_results if r["passed"])
    failed_count = len(all_results) - passed_count
    total_issues = sum(len(r["issues"]) for _, r in all_results)

    if format == "json":
        import json

        output = json.dumps(
            {
                "summary": {
                    "passed": passed_count,
                    "failed": failed_count,
                    "total_files": len(all_results),
                    "total_issues": total_issues,
                },
                "results": [{"file": str(f), **r} for f, r in all_results],
            },
            indent=2,
            ensure_ascii=False,
        )
    else:
        lines = []
        for filepath, result in all_results:
            if result["passed"]:
                lines.append(f"✅ {filepath}")
            else:
                lines.append(f"❌ {filepath} ({len(result['issues'])} issues)")
                for issue in result["issues"][:5]:
                    lines.append(f"   Line {issue['line']}: [{issue['type']}] {issue['message']}")
                if len(result["issues"]) > 5:
                    lines.append(f"   ... and {len(result['issues']) - 5} more")
        lines.append(f"\nSummary: {passed_count} passed, {failed_count} failed, {total_issues} issues")
        output = "\n".join(lines)

    return failed_count == 0, output


def run_governance_audit(
    full: bool = False,
    validate_docs: bool = False,
    check_ai_sdlc: bool = False,
    audit_hallucination: bool = False,
    check_index: bool = False,
) -> tuple[bool, str]:
    """运行治理审计"""
    # 直接调用 governance-auditor 的函数
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".jcode" / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "governance_auditor",
        Path(__file__).resolve().parent.parent.parent / ".jcode" / "scripts" / "governance-auditor.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("Failed to load governance_auditor module")
    governance_auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(governance_auditor)

    lint = governance_auditor.lint
    format_check = governance_auditor.format_check
    typecheck = governance_auditor.typecheck
    test = governance_auditor.test
    validate_governance_docs = governance_auditor.validate_governance_docs
    check_ai_sdlc_compliance = governance_auditor.check_ai_sdlc_compliance
    audit_hallucination_risks = governance_auditor.audit_hallucination_risks

    checks = []
    if full or validate_docs:
        checks.append(("Governance Docs", validate_governance_docs))
    if full or check_ai_sdlc:
        checks.append(("AI-SDLC Compliance", check_ai_sdlc_compliance))
    if full or audit_hallucination:
        checks.append(("Hallucination Risk", audit_hallucination_risks))
    if check_index:
        # 调用 governance-docs-validator.py check-index
        def _check_index() -> bool:
            import subprocess

            result = subprocess.run(
                [sys.executable, ".jcode/scripts/governance-docs-validator.py", "check-index"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0

        checks.append(("Index References", _check_index))
    if full:
        checks = [
            ("Lint", lint),
            ("Format", format_check),
            ("Type Check", typecheck),
            ("Test", test),
            *checks,
        ]

    if not checks:
        checks = [
            ("Lint", lint),
            ("Format", format_check),
            ("Type Check", typecheck),
            ("Test", test),
            ("Governance Docs", validate_governance_docs),
            ("AI-SDLC Compliance", check_ai_sdlc_compliance),
        ]

    failed = []
    output_lines = []

    for name, func in checks:
        passed = func()
        status = "✅ PASS" if passed else "❌ FAIL"
        output_lines.append(f"  {status}: {name}")
        if not passed:
            failed.append(name)

    output = "\n".join(output_lines)
    if failed:
        output += f"\n\nFailed checks: {', '.join(failed)}"

    return len(failed) == 0, output


# =============================================================================
# CLI
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="统一 Hook 运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hooks_runner.py lint
  hooks_runner.py format
  hooks_runner.py typecheck
  hooks_runner.py test
  hooks_runner.py security
  hooks_runner.py language-rules --path tools/scripts --lang python
  hooks_runner.py quality-gate --path tools/scripts --full
  hooks_runner.py governance-audit --full
  hooks_runner.py full
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # lint
    subparsers.add_parser("lint", help="Run ruff lint check")

    # format
    subparsers.add_parser("format", help="Run ruff format check")

    # typecheck
    subparsers.add_parser("typecheck", help="Run mypy type check")

    # test
    subparsers.add_parser("test", help="Run pytest test suite")

    # security
    subparsers.add_parser("security", help="Run security scan (bandit + pip-audit)")

    # language-rules
    lr_parser = subparsers.add_parser("language-rules", help="Run language-specific rules validation")
    lr_parser.add_argument("--path", type=Path, default=Path("."), help="Path to validate")
    lr_parser.add_argument("--lang", help="Language (auto-detect if not specified)")

    # quality-gate
    qg_parser = subparsers.add_parser("quality-gate", help="Run AI Quality Gate checks")
    qg_parser.add_argument("--path", type=Path, default=Path("tools/scripts"), help="Path to check")
    qg_parser.add_argument("--full", action="store_true", help="Run all checks")
    qg_parser.add_argument("--check-annotation", action="store_true", help="Check AI annotation")
    qg_parser.add_argument("--check-security", action="store_true", help="Check security patterns")
    qg_parser.add_argument("--check-type", action="store_true", help="Check type safety")
    qg_parser.add_argument("--check-error", action="store_true", help="Check error handling")
    qg_parser.add_argument("--check-structure", action="store_true", help="Check code structure")
    qg_parser.add_argument("--check-patterns", action="store_true", help="Check all anti-patterns")
    qg_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # governance-audit
    ga_parser = subparsers.add_parser("governance-audit", help="Run Governance Auditor checks")
    ga_parser.add_argument("--full", action="store_true", help="Run all governance checks")
    ga_parser.add_argument("--validate-docs", action="store_true", help="Validate governance docs")
    ga_parser.add_argument("--check-ai-sdlc", action="store_true", help="Check AI-SDLC compliance")
    ga_parser.add_argument("--audit-hallucination", action="store_true", help="Audit hallucination risks")
    ga_parser.add_argument("--check-index", action="store_true", help="Check index references")

    # full
    subparsers.add_parser(
        "full", help="Run all checks (lint, format, typecheck, test, security, quality-gate, governance-audit)"
    )

    args = parser.parse_args()

    # 执行对应命令
    if args.command == "lint":
        passed, output = run_lint()
        print(output)
        return 0 if passed else 1

    elif args.command == "format":
        passed, output = run_format_check()
        print(output)
        return 0 if passed else 1

    elif args.command == "typecheck":
        passed, output = run_typecheck()
        print(output)
        return 0 if passed else 1

    elif args.command == "test":
        passed, output = run_tests()
        print(output)
        return 0 if passed else 1

    elif args.command == "security":
        passed, output = run_security()
        print(output)
        return 0 if passed else 1

    elif args.command == "language-rules":
        passed, output = run_language_rules(args.path, args.lang)
        print(output)
        return 0 if passed else 1

    elif args.command == "quality-gate":
        passed, output = run_quality_gate(
            args.path,
            full=args.full,
            check_annotation=args.check_annotation,
            check_security=args.check_security,
            check_type=args.check_type,
            check_error=args.check_error,
            check_structure=args.check_structure,
            check_patterns=args.check_patterns,
            format=args.format,
        )
        print(output)
        return 0 if passed else 1

    elif args.command == "governance-audit":
        passed, output = run_governance_audit(
            full=args.full,
            validate_docs=args.validate_docs,
            check_ai_sdlc=args.check_ai_sdlc,
            audit_hallucination=args.audit_hallucination,
            check_index=args.check_index,
        )
        print(output)
        return 0 if passed else 1

    elif args.command == "full":
        print("=" * 60)
        print("  FULL HOOKS RUNNER - 完整检查套件")
        print("=" * 60)

        all_passed = True

        # 1. Lint
        print("\n📋 1/7: Lint Check")
        passed, output = run_lint()
        print(output)
        if not passed:
            all_passed = False

        # 2. Format
        print("\n📋 2/7: Format Check")
        passed, output = run_format_check()
        print(output)
        if not passed:
            all_passed = False

        # 3. Type Check
        print("\n📋 3/7: Type Check")
        passed, output = run_typecheck()
        print(output)
        if not passed:
            all_passed = False

        # 4. Tests
        print("\n📋 4/7: Test Suite")
        passed, output = run_tests()
        print(output)
        if not passed:
            all_passed = False

        # 5. Security
        print("\n📋 5/7: Security Scan")
        passed, output = run_security()
        print(output)
        if not passed:
            all_passed = False

        # 6. Quality Gate
        print("\n📋 6/7: AI Quality Gate")
        passed, output = run_quality_gate(Path("tools/scripts"), full=True)
        print(output)
        if not passed:
            all_passed = False

        # 7. Governance Audit
        print("\n📋 7/7: Governance Audit")
        passed, output = run_governance_audit(full=True)
        print(output)
        if not passed:
            all_passed = False

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL CHECKS PASSED")
        else:
            print("❌ SOME CHECKS FAILED")
        print("=" * 60)

        return 0 if all_passed else 1

    # Unknown command - should not reach here due to required=True, but mypy needs it
    print(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
