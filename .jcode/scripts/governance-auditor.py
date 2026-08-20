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
    python .jcode/scripts/governance-auditor.py ai-quality-gate
    python .jcode/scripts/governance-auditor.py full
"""

import re
import subprocess
import sys
from pathlib import Path

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
# 格式: (pattern, description, exclude_files_list, exclude_pattern)
# exclude_files_list: 文件名列表，如果文件名匹配则跳过
# exclude_pattern: 正则模式，如果内容匹配则跳过
UNSAFE_PATTERNS = [
    (
        r"eval\(",
        "eval 调用 - 代码注入风险",
        [
            "auto_fix.py",
            "generate_fixes.py",
            "ai_quality_gate.py",
            "rule_editor.py",
            "hallucination_detector.py",
            "fix_heuristics.py",
        ],
        None,
    ),
    (
        r"exec\(",
        "exec 调用 - 代码注入风险",
        [
            "auto_fix.py",
            "generate_fixes.py",
            "ai_quality_gate.py",
            "rule_editor.py",
            "hallucination_detector.py",
            "fix_heuristics.py",
        ],
        None,
    ),
    (
        r"os\.system\(",
        "os.system() - 应使用 subprocess",
        [
            "generate_fixes.py",
            "hallucination_detector.py",
            "fix_heuristics.py",
            "auto_fix.py",
        ],
        None,
    ),
    (
        r"pickle\.loads?\(",
        "pickle - 反序列化风险",
        ["generate_fixes.py", "hallucination_detector.py"],
        None,
    ),
    (
        r"yaml\.load\((?!.*Loader)",
        "yaml.load 不安全 - 应使用 safe_load",
        [],
        r"yaml\.load\((?!.*Loader)",
    ),
]


def _check_unsafe_patterns(
    content: str, patterns: list, filepath: str = ""
) -> list[str]:
    """检查不安全模式，支持排除文件和排除模式"""
    risks = []
    filename = Path(filepath).name if filepath else ""
    for pattern_item in patterns:
        pattern = pattern_item[0]
        desc = pattern_item[1]
        exclude_files = pattern_item[2] if len(pattern_item) > 2 else []
        exclude_pattern = pattern_item[3] if len(pattern_item) > 3 else None

        # 如果文件名在排除列表中，跳过
        if filename in exclude_files:
            continue

        # 如果有排除模式且匹配，跳过
        if exclude_pattern and re.search(exclude_pattern, content):
            continue

        if re.search(pattern, content):
            risks.append(desc)
    return risks


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
    code, output = run_command(
        [sys.executable, "-m", "mypy", "tools/scripts/", "--ignore-missing-imports"]
    )
    print_check("mypy", code == 0, output)
    if code != 0:
        print(output)
    return code == 0


def test() -> bool:
    """运行 pytest 测试套件"""
    print_section("测试套件")
    code, output = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--cov=tools/scripts",
            "--cov-report=term-missing",
            "--tb=short",
        ]
    )
    print_check("pytest", code == 0, output)
    if code != 0:
        print(output)
    return code == 0


def security() -> bool:
    """运行安全扫描"""
    print_section("安全扫描")

    # bandit
    code1, output1 = run_command(
        [
            "bandit",
            "-r",
            "tools/scripts/",
            "-f",
            "json",
            "-o",
            "bandit-report.json",
            "-ll",
        ]
    )
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
    """验证15个治理层文档格式完整性。

    统一入口: 委托 governance-docs-validator（唯一实现，避免重复逻辑漂移）。
    """
    print_section("治理文档验证")
    validator_script = Path(__file__).resolve().parent / "governance-docs-validator.py"
    code, output = run_command([sys.executable, str(validator_script), "validate"])
    if output.strip():
        print(output.strip())
    return code == 0


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
        file_risks = _check_unsafe_patterns(content, UNSAFE_PATTERNS, py_file.name)
        for risk in file_risks:
            rel = py_file.relative_to(root)
            risks.append(f"{rel}: {risk}")

    # 文档绝对化声明
    # "100%" 只在断言性语句中标记（如 "永远100%"、"保证100%"），不在度量值中标记（如 "覆盖率100%"）
    abs_patterns = [
        (r"永远\s*100%", "永远100%"),
        (r"绝对\s*100%", "绝对100%"),
        (r"保证\s*100%", "保证100%"),
        (r"从不\s*100%", "从不100%"),
        (r"永远", "永远"),
        (r"绝对(?!化)", "绝对"),
        (r"从不", "从不"),
    ]
    for md_file in (root / "docs" / "efficiency").rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.split("\n"), 1):
            # 跳过标题行、代码块、图表行
            stripped = line.strip()
            if (
                stripped.startswith("#")
                or stripped.startswith("```")
                or stripped.startswith("|")
                or stripped.startswith("←")
            ):
                continue
            for pat, desc in abs_patterns:
                if re.search(pat, line) and "例外" not in line and "除非" not in line:
                    rel = md_file.relative_to(root)
                    risks.append(f"{rel}:{line_num}: 绝对化声明 '{desc}'")

    passed = len(risks) == 0
    print_check(f"幻觉风险 ({len(risks)} 个)", passed)
    if risks:
        for risk in risks[:20]:
            print(f"  - {risk}")
        if len(risks) > 20:
            print(f"  ... 还有 {len(risks) - 20} 个风险")
    return passed


def ai_quality_gate() -> bool:
    """运行 AI 代码质量门禁 (整合 ai_quality_gate.py)"""
    print_section("🛡️ AI 代码质量门禁")
    root = get_project_root()
    script = root / "tools" / "scripts" / "ai_quality_gate.py"
    if not script.exists():
        print(f"⚠️  未找到 {script}")
        return True  # 非阻断
    cmd = [
        sys.executable,
        str(script),
        "--check-annotation",
        "--check-security",
        "--check-patterns",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root)
    passed = result.returncode == 0
    print_check("人工智能质量门禁", passed, result.stdout + result.stderr)
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
        ("AI Quality Gate", ai_quality_gate),
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
        print(
            "Actions: lint, format, typecheck, test, security, "
            "validate-governance-docs, check-ai-sdlc-compliance, "
            "audit-hallucination-risks, ai-quality-gate, full"
        )
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
        "ai-quality-gate": lambda: 0 if ai_quality_gate() else 1,
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
