#!/usr/bin/env python3
"""
jcode Skill Runner - 治理审计员

用法:
    python .jcode/scripts/governance-auditor.py lint
    python .jcode/scripts/governance-auditor.py format
    python .jcode/scripts/governance-auditor.py typecheck
    python .jcode/scripts/governance-auditor.py test
    python .jcode/scripts/governance-auditor.py security
    python .jcode/scripts/governance-auditor.py full
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str]:
    """运行命令并返回结果"""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent)
    return result.returncode, result.stdout + result.stderr


def lint() -> None:
    """运行 ruff lint 检查"""
    print("🔍 运行 ruff lint 检查...")
    code, output = run_command(["ruff", "check", "."])
    print(output)
    if code == 0:
        print("✅ lint 检查通过")
    else:
        print("❌ lint 检查失败")
    sys.exit(code)


def format_check() -> None:
    """运行 ruff format 检查"""
    print("🎨 运行 ruff format 检查...")
    code, output = run_command(["ruff", "format", "--check", "."])
    print(output)
    if code == 0:
        print("✅ format 检查通过")
    else:
        print("❌ format 检查失败")
    sys.exit(code)


def typecheck() -> None:
    """运行 mypy 类型检查"""
    print("🔬 运行 mypy 类型检查...")
    code, output = run_command([
        sys.executable, "-m", "mypy", "tools/scripts/", "--ignore-missing-imports"
    ])
    print(output)
    if code == 0:
        print("✅ 类型检查通过")
    else:
        print("❌ 类型检查失败")
    sys.exit(code)


def test() -> None:
    """运行 pytest 测试套件"""
    print("🧪 运行 pytest 测试套件...")
    code, output = run_command([
        sys.executable, "-m", "pytest", "tests/", "-v", "--cov=tools/scripts", "--cov-report=term-missing"
    ])
    print(output)
    if code == 0:
        print("✅ 测试通过")
    else:
        print("❌ 测试失败")
    sys.exit(code)


def security() -> None:
    """运行安全扫描"""
    print("🔒 运行安全扫描...")
    # bandit
    code1, output1 = run_command([
        "bandit", "-r", "tools/scripts/", "-f", "json", "-o", "bandit-report.json"
    ])
    print("Bandit 结果:")
    print(output1)

    # pip-audit
    code2, output2 = run_command(["pip-audit", "--desc"])
    print("Pip-audit 结果:")
    print(output2)

    if code1 == 0 and code2 == 0:
        print("✅ 安全扫描通过")
    else:
        print("⚠️ 安全扫描发现问题")
    sys.exit(max(code1, code2))


def full() -> None:
    """运行完整审计"""
    print("🚀 运行完整审计...")
    print("=" * 50)

    checks = [
        ("Lint", lint),
        ("Format", format_check),
        ("Type Check", typecheck),
        ("Test", test),
    ]

    failed = []
    for name, func in checks:
        print(f"\n{'=' * 50}")
        print(f"执行 {name}...")
        try:
            func()
        except SystemExit:
            failed.append(name)

    print("\n" + "=" * 50)
    if failed:
        print(f"❌ 以下检查失败: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("✅ 所有检查通过")
        sys.exit(0)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: governance-auditor.py <action>")
        print("Actions: lint, format, typecheck, test, security, full")
        sys.exit(1)

    action = sys.argv[1]

    actions = {
        "lint": lint,
        "format": format_check,
        "typecheck": typecheck,
        "test": test,
        "security": security,
        "full": full,
    }

    if action in actions:
        actions[action]()
    else:
        print(f"未知 action: {action}")
        print("可用 actions: " + ", ".join(actions.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()
