#!/usr/bin/env python3
"""
jcode Skill Runner - 治理审计员

用法:
    python .jcode/scripts/governance-auditor.py lint
    python .jcode/scripts/governance-auditor.py format
    python .jcode/scripts/governance-auditor.py typecheck
    python .jcode/scripts/governance-auditor.py test
    python .jcode/scripts/governance-auditor.py security
    python .jcode/scripts/governance-auditor.py validate-governance-docs
    python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance
    python .jcode/scripts/governance-auditor.py audit-hallucination-risks
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


def validate_governance_docs() -> None:
    """验证治理层文档格式完整性"""
    print("📋 验证治理层文档格式完整性...")
    governance_docs = [
        "docs/efficiency/ai-code-generation-quality.md",
        "docs/efficiency/ai-model-selection.md",
        "docs/efficiency/ai-sdlc.md",
        "docs/efficiency/ai-code-review-checklist.md",
        "docs/efficiency/ai-nondeterministic-testing.md",
        "docs/efficiency/ai-hallucination-mitigation.md",
        "docs/efficiency/ai-code-licensing.md",
        "docs/efficiency/ai-dev-environment.md",
        "docs/efficiency/ai-context-window-management.md",
        "docs/efficiency/ai-performance-benchmarks.md",
        "docs/efficiency/ai-debugging-standards.md",
        "docs/efficiency/ai-version-control.md",
        "docs/efficiency/ai-deployment-operations.md",
        "docs/efficiency/ai-developer-training.md",
        "docs/efficiency/ai-dev-toolchain.md",
    ]

    issues = []
    for doc_path in governance_docs:
        path = Path(doc_path)
        if not path.exists():
            issues.append(f"Missing: {doc_path}")
            continue

        content = path.read_text(encoding="utf-8")

        # 检查 frontmatter
        if not content.startswith("---"):
            issues.append(f"{doc_path}: Missing frontmatter")
            continue

        fm_end = content.find("---", 3)
        if fm_end == -1:
            issues.append(f"{doc_path}: Unclosed frontmatter")
            continue

        fm = content[3:fm_end]
        required = ["title", "description", "category", "tags", "difficulty"]
        for field in required:
            if field + ":" not in fm:
                issues.append(f"{doc_path}: Missing field '{field}'")

        # 检查导航部分
        if "## 导航" not in content and "## Navigation" not in content:
            issues.append(f"{doc_path}: Missing navigation section")

        # 检查相关文档
        if "相关文档" not in content and "## See Also" not in content:
            issues.append(f"{doc_path}: Missing related docs section")

    if issues:
        print(f"\n❌ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print(f"✅ {len(governance_docs)} 个治理文档验证通过")
        sys.exit(0)


def check_ai_sdlc_compliance() -> None:
    """检查 AI-SDLC 合规性"""
    print("🔄 检查 AI-SDLC 合规性...")
    issues = []

    # 检查 CI/CD 配置
    ci_path = Path(".github/workflows/ci.yml")
    if ci_path.exists():
        ci_content = ci_path.read_text(encoding="utf-8")
        required_jobs = ["pre-commit", "lint", "type-check", "test"]
        for job in required_jobs:
            if job not in ci_content:
                issues.append(f"CI/CD missing job: {job}")
    else:
        issues.append("CI/CD configuration not found")

    # 检查测试配置
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "pytest" not in content:
            issues.append("pytest not configured in pyproject.toml")
    else:
        issues.append("pyproject.toml not found")

    # 检查 pre-commit 配置
    precommit = Path(".pre-commit-config.yaml")
    if not precommit.exists():
        issues.append("pre-commit configuration not found")

    if issues:
        print(f"\n❌ AI-SDLC 合规检查失败 ({len(issues)} 个问题):")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("✅ AI-SDLC 合规检查通过")
        sys.exit(0)


def audit_hallucination_risks() -> None:
    """审计幻觉风险"""
    print("🔍 审计幻觉风险...")
    risks = []

    # 检查代码中是否有不安全的模式
    unsafe_patterns = [
        (r'eval\(', "eval() usage - potential code injection"),
        (r'exec\(', "exec() usage - potential code injection"),
        (r'os\.system\(', "os.system() usage - use subprocess instead"),
        (r'pickle\.loads?\(', "pickle usage - potential deserialization risk"),
        (r'yaml\.load\((?!.*Loader)', "yaml.load without Loader - use safe_load"),
    ]

    import re
    for py_file in Path("tools/scripts").rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pattern, desc in unsafe_patterns:
            if re.search(pattern, content):
                risks.append(f"{py_file}: {desc}")

    # 检查文档中的断言声明
    for md_file in Path("docs/efficiency").rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        # 检查是否有绝对化声明
        absolute_patterns = ["100%", "永远", "绝对", "从不"]
        for line_num, line in enumerate(content.split("\n"), 1):
            for pattern in absolute_patterns:
                if pattern in line and "例外" not in line:
                    risks.append(f"{md_file}:{line_num}: Absolute claim '{pattern}' found")

    if risks:
        print(f"\n⚠️ 发现 {len(risks)} 个风险:")
        for risk in risks[:20]:
            print(f"  - {risk}")
        if len(risks) > 20:
            print(f"  ... 还有 {len(risks) - 20} 个风险")
        sys.exit(1)
    else:
        print("✅ 幻觉风险审计通过")
        sys.exit(0)


def full() -> None:
    """运行完整审计"""
    print("🚀 运行完整审计...")
    print("=" * 50)

    checks = [
        ("Lint", lint),
        ("Format", format_check),
        ("Type Check", typecheck),
        ("Test", test),
        ("Governance Docs", validate_governance_docs),
        ("AI-SDLC Compliance", check_ai_sdlc_compliance),
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
        print("Actions: lint, format, typecheck, test, security, validate-governance-docs, check-ai-sdlc-compliance, audit-hallucination-risks, full")
        sys.exit(1)

    action = sys.argv[1]

    actions = {
        "lint": lint,
        "format": format_check,
        "typecheck": typecheck,
        "test": test,
        "security": security,
        "validate-governance-docs": validate_governance_docs,
        "check-ai-sdlc-compliance": check_ai_sdlc_compliance,
        "audit-hallucination-risks": audit_hallucination_risks,
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
