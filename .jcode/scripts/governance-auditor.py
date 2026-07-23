#!/usr/bin/env python3
"""
jcode Skill Runner - 治理审计员 (v2.0)

重构版: 使用 _common.py 共享模块，修复 sys.exit 早期退出问题。
所有子检查返回 bool 而非直接 sys.exit，由 main() 统一处理退出码。

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

import re
import sys

from _common import get_project_root, print_check, print_section, run_command

# ── 15 个 ────────────────────────────────────────────────
GOVERNANCE_DOCS = [
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

# ── 代码不安全模式 ────────────────────────────────────────────────
UNSAFE_PATTERNS = [
    (r"eval\(", "eval() - 代码注入风险"),
    (r"exec\(", "exec() - 代码注入风险"),
    (r"os\.system\(", "os.system() - 应使用 subprocess"),
    (r"pickle\.loads?\(", "pickle - 反序列化风险"),
    (r"yaml\.load\((?!.*Loader)", "yaml.load 不安全 - 应使用 safe_load"),
]


def lint() -> bool:
    """运行 ruff lint 检查"""
    print_section("Lint 检查")
    code, output = run_command(["ruff", "check", "."])
    print_check("ruff check", code == 0, output)
    if code != 0:
        print(output)
    return code == 0


def format_check() -> bool:
    """运行 ruff format 检查"""
    print_section("Format 检查")
    code, output = run_command(["ruff", "format", "--check", "."])
    print_check("ruff format", code == 0, output)
    if code != 0:
        print(output)
    return code == 0


def typecheck() -> bool:
    """运行 mypy 类型检查"""
    print_section("类型检查")
    code, output = run_command([
        sys.executable, "-m", "mypy", "tools/scripts/", "--ignore-missing-imports"
    ])
    print_check("mypy", code == 0, output)
    if code != 0:
        print(output)
    return code == 0


def test() -> bool:
    """运行 pytest 测试套件"""
    print_section("测试套件")
    code, output = run_command([
        sys.executable, "-m", "pytest", "tests/", "-v",
        "--cov=tools/scripts", "--cov-report=term-missing", "--tb=short"
    ])
    print_check("pytest", code == 0, output)
    if code != 0:
        print(output)
    return code == 0


def security() -> bool:
    """运行安全扫描"""
    print_section("安全扫描")

    # bandit
    code1, output1 = run_command([
        "bandit", "-r", "tools/scripts/", "-f", "json", "-o", "bandit-report.json", "-ll"
    ])
    print_check("bandit", code1 == 0, output1)

    # pip-audit
    code2, output2 = run_command(["pip-audit", "--desc"])
    print_check("pip-audit", code2 == 0, output2)

    if code1 != 0:
        print(output1)
    if code2 != 0:
        print(output2)
    return code1 == 0 and code2 == 0


def validate_governance_docs() -> bool:
    """验证15个治理层文档格式完整性"""
    print_section("治理文档验证")
    issues: list[str] = []

    for doc_path in GOVERNANCE_DOCS:
        path = get_project_root() / doc_path
        if not path.exists():
            issues.append(f"Missing: {doc_path}")
            continue

        content = path.read_text(encoding="utf-8")

        # frontmatter 检查
        if not content.startswith("---"):
            issues.append(f"{doc_path}: Missing frontmatter")
            continue

        fm_end = content.find("---", 3)
        if fm_end == -1:
            issues.append(f"{doc_path}: Unclosed frontmatter")
            continue

        fm = content[3:fm_end]
        for field in ["title", "description", "category", "tags", "difficulty"]:
            if f"{field}:" not in fm:
                issues.append(f"{doc_path}: Missing field '{field}'")

        # 导航检查
        if "## 导航" not in content and "## Navigation" not in content:
            issues.append(f"{doc_path}: Missing navigation section")

        # 相关文档检查
        if "相关文档" not in content and "## See Also" not in content:
            issues.append(f"{doc_path}: Missing related docs section")

    passed = len(issues) == 0
    print_check(f"治理文档 ({len(GOVERNANCE_DOCS)} 个)", passed)
    if issues:
        for issue in issues:
            print(f"  - {issue}")
    return passed


def check_ai_sdlc_compliance() -> bool:
    """检查 AI-SDLC 合规性"""
    print_section("AI-SDLC 合规检查")
    issues: list[str] = []
    root = get_project_root()

    # CI/CD 配置
    ci_path = root / ".github" / "workflows" / "ci.yml"
    if ci_path.exists():
        ci_content = ci_path.read_text(encoding="utf-8")
        for job in ["pre-commit", "lint", "type-check", "test"]:
            if job not in ci_content:
                issues.append(f"CI/CD missing job: {job}")
    else:
        issues.append("CI/CD configuration not found")

    # pytest 配置
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        if "pytest" not in pyproject.read_text(encoding="utf-8"):
            issues.append("pytest not configured in pyproject.toml")
    else:
        issues.append("pyproject.toml not found")

    # pre-commit 配置
    if not (root / ".pre-commit-config.yaml").exists():
        issues.append("pre-commit configuration not found")

    passed = len(issues) == 0
    print_check("AI-SDLC 合规", passed)
    if issues:
        for issue in issues:
            print(f"  - {issue}")
    return passed


def audit_hallucination_risks() -> bool:
    """审计幻觉风险"""
    print_section("幻觉风险审计")
    risks: list[str] = []
    root = get_project_root()

    # 代码不安全模式
    for py_file in (root / "tools" / "scripts").rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pattern, desc in UNSAFE_PATTERNS:
            if re.search(pattern, content):
                rel = py_file.relative_to(root)
                risks.append(f"{rel}: {desc}")

    # 文档绝对化声明
    abs_patterns = ["100%", "永远", "绝对", "从不"]
    for md_file in (root / "docs" / "efficiency").rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.split("\n"), 1):
            for pat in abs_patterns:
                if pat in line and "例外" not in line:
                    rel = md_file.relative_to(root)
                    risks.append(f"{rel}:{line_num}: 绝对化声明 '{pat}'")

    passed = len(risks) == 0
    print_check(f"幻觉风险 ({len(risks)} 个)", passed)
    if risks:
        for risk in risks[:20]:
            print(f"  - {risk}")
        if len(risks) > 20:
            print(f"  ... 还有 {len(risks) - 20} 个风险")
    return passed


def full() -> int:
    """运行失败数量"""
    print_section("🚀 完整治理审计 (v2.0)")

    checks = [
        ("Lint", lint),
        ("Format", format_check),
        ("Type Check", typecheck),
        ("Test", test),
        ("Governance Docs", validate_governance_docs),
        ("AI-SDLC Compliance", check_ai_sdlc_compliance),
    ]

    failed: list[str] = []
    for name, func in checks:
        if not func():
            failed.append(name)

    print_section("审计结果")
    if failed:
        print(f"❌ 失败: {', '.join(failed)}")
        return len(failed)
    else:
        print("✅ 所有检查通过")
        return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: governance-auditor.py <action>")
        print("Actions: lint, format, typecheck, test, security, "
              "validate-governance-docs, check-ai-sdlc-compliance, "
              "audit-hallucination-risks, full")
        sys.exit(1)

    action = sys.argv[1]

    action_map = {
        "lint": lambda: 0 if lint() else 1,
        "format": lambda: 0 if format_check() else 1,
        "typecheck": lambda: 0 if typecheck() else 1,
        "test": lambda: 0 if test() else 1,
        "security": lambda: 0 if security() else 1,
        "validate-governance-docs": lambda: 0 if validate_governance_docs() else 1,
        "check-ai-sdlc-compliance": lambda: 0 if check_ai_sdlc_compliance() else 1,
        "audit-hallucination-risks": lambda: 0 if audit_hallucination_risks() else 1,
        "full": full,
    }

    if action in action_map:
        sys.exit(action_map[action]())
    else:
        print(f"❌ 未知 action: {action}")
        print(f"可用 actions: {', '.join(action_map.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
