#!/usr/bin/env python3
"""
jcode Skill Runner - 治理审计员 (v3.0 - 多语言支持)

重构版: 使用 language_registry 实现多语言工具链支持
所有子检查返回 bool 而非直接 sys.exit，由 main() 统一处理退出码。

用法:
    python .jcode/scripts/governance-auditor.py lint [--lang python|typescript|...]
    python .jcode/scripts/governance-auditor.py format [--lang python|...]
    python .jcode/scripts/governance-auditor.py typecheck [--lang python|...]
    python .jcode/scripts/governance-auditor.py test [--lang python|...]
    python .jcode/scripts/governance-auditor.py security [--lang python|...]
    python .jcode/scripts/governance-auditor.py validate-governance-docs
    python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance
    python .jcode/scripts/governance-auditor.py audit-hallucination-risks
    python .jcode/scripts/governance-auditor.py ai-quality-gate
    python .jcode/scripts/governance-auditor.py full [--lang python,typescript]
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "scripts"))
from _common import get_project_root, print_check, print_section, run_command
from language_registry import (
    EXTENSION_MAP,
    Language,
    ToolCategory,
    detect_language,
    get_tool,
    list_supported_languages,
)

# ── 15 个治理层文档 ────────────────────────────────────────────────
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
UNSAFE_PATTERNS: list[tuple[str, str, list[str], str | None]] = [
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
    content: str, patterns: list[tuple[str, str, list[str], str | None]], filepath: str = ""
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


def _parse_languages(lang_str: str) -> list[Language]:
    """解析逗号分隔的语言字符串"""
    languages = []
    for part in lang_str.split(","):
        part = part.strip()
        if part:
            try:
                languages.append(Language(part.lower()))
            except ValueError:
                from language_registry import LANGUAGE_ALIASES

                if part.lower() in LANGUAGE_ALIASES:
                    languages.append(LANGUAGE_ALIASES[part.lower()])
                else:
                    print(f"  ⚠️  未知语言: {part}，跳过")
    return languages


def _detect_project_languages(project_root: Path) -> list[Language]:
    """检测项目中使用的所有语言"""
    languages: list[Language] = []

    # 1. 通过配置文件检测主要语言
    main_lang = detect_language(project_root)
    if main_lang:
        languages.append(main_lang)

    # 2. 扫描所有扩展名，统计语言分布
    ext_counts: dict[Language, int] = {}
    for ext, lang in EXTENSION_MAP.items():
        count = len(list(project_root.rglob(f"*{ext}")))
        if count > 0:
            ext_counts[lang] = ext_counts.get(lang, 0) + count

    # 按文件数排序，添加前 3 种语言
    for lang in sorted(ext_counts, key=lambda k: ext_counts.get(k, 0), reverse=True)[:3]:
        if lang not in languages:
            languages.append(lang)

    return languages


def _run_tool_for_language(
    language: Language,
    category: ToolCategory,
    project_root: Path,
    check_only: bool = False,
) -> tuple[bool, str]:
    """使用语言工具链运行特定类别工具"""
    tool = get_tool(language, category)
    if tool is None:
        return False, f"  ⚠️  {language.value}: {category.value} 工具未配置"

    # 检查工具是否可用
    try:
        result = subprocess.run(
            [tool.command, tool.version_flag],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False, f"  ❌ {language.value}: {tool.command} 不可用 ({tool.install_hint})"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, f"  ❌ {language.value}: {tool.command} 未安装 ({tool.install_hint})"

    # 构建命令
    cmd = [tool.command]
    if check_only and tool.check_args:
        cmd.extend(tool.check_args)
    else:
        cmd.extend(tool.args)

    print(f"  🔧 {language.value}: 运行 {category.value} ({' '.join(cmd)})")

    try:
        proc_result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = proc_result.stdout
        if proc_result.stderr:
            output += "\n" + proc_result.stderr

        passed = proc_result.returncode == 0
        status = "✅" if passed else "❌"
        return passed, f"  {status} {language.value}: {category.value} {'通过' if passed else '失败'}\n{output}"
    except subprocess.TimeoutExpired:
        return False, f"  ❌ {language.value}: {category.value} 超时 (600s)"
    except Exception as e:
        return False, f"  ❌ {language.value}: {category.value} 错误 - {e}"


def _run_check_for_languages(
    languages: list[Language],
    category: ToolCategory,
    project_root: Path,
    check_only: bool = False,
) -> tuple[bool, str]:
    """为多个语言运行检查"""
    all_passed = True
    outputs = []

    for lang in languages:
        passed, output = _run_tool_for_language(lang, category, project_root, check_only)
        all_passed = all_passed and passed
        outputs.append(output)

    return all_passed, "\n".join(outputs)


def lint(lang: str | None = None) -> bool:
    """运行 lint 检查 - 支持多语言"""
    print_section("Lint 检查")
    root = get_project_root()

    if lang:
        languages = _parse_languages(lang)
    else:
        languages = _detect_project_languages(root)

    if not languages:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        languages = [Language.PYTHON]

    passed, output = _run_check_for_languages(languages, ToolCategory.LINT, root, check_only=True)
    print_check("lint", passed, output)
    return passed


def format_check(lang: str | None = None) -> bool:
    """运行 format 检查 - 支持多语言"""
    print_section("Format 检查")
    root = get_project_root()

    if lang:
        languages = _parse_languages(lang)
    else:
        languages = _detect_project_languages(root)

    if not languages:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        languages = [Language.PYTHON]

    passed, output = _run_check_for_languages(languages, ToolCategory.FORMAT, root, check_only=True)
    print_check("format", passed, output)
    return passed


def typecheck(lang: str | None = None) -> bool:
    """运行类型检查 - 支持多语言"""
    print_section("类型检查")
    root = get_project_root()

    if lang:
        languages = _parse_languages(lang)
    else:
        languages = _detect_project_languages(root)

    if not languages:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        languages = [Language.PYTHON]

    passed, output = _run_check_for_languages(languages, ToolCategory.TYPECHECK, root)
    print_check("typecheck", passed, output)
    return passed


def test(lang: str | None = None) -> bool:
    """运行测试套件 - 支持多语言"""
    print_section("测试套件")
    root = get_project_root()

    if lang:
        languages = _parse_languages(lang)
    else:
        languages = _detect_project_languages(root)

    if not languages:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        languages = [Language.PYTHON]

    passed, output = _run_check_for_languages(languages, ToolCategory.TEST, root)
    print_check("test", passed, output)
    return passed


def security(lang: str | None = None) -> bool:
    """运行安全扫描 - 支持多语言"""
    print_section("安全扫描")
    root = get_project_root()

    if lang:
        languages = _parse_languages(lang)
    else:
        languages = _detect_project_languages(root)

    if not languages:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        languages = [Language.PYTHON]

    passed, output = _run_check_for_languages(languages, ToolCategory.SECURITY, root)
    print_check("security", passed, output)
    return passed


def validate_governance_docs() -> bool:
    """验证15个治理层文档格式完整性。

    统一入口: 委托 governance-docs-validator（唯一实现，避免重复逻辑漂移）。
    """
    print_section("治理文档验证")
    validator_script = Path(__file__).resolve().parent / "governance-docs-validator.py"
    code, output = run_command([sys.executable, str(validator_script), "validate"])
    if output.strip():
        print(output.strip())
    return bool(code == 0)


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


def full(lang: str | None = None) -> int:
    """运行完整治理审计"""
    print_section("🚀 完整治理审计 (v3.0 - 多语言)")

    if lang:
        languages = _parse_languages(lang)
    else:
        languages = _detect_project_languages(get_project_root())

    if not languages:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        languages = [Language.PYTHON]

    print(f"检测语言: {', '.join(lang.value for lang in languages)}")

    checks: list[tuple[str, Callable[[], bool]]] = [
        ("Lint", lambda: lint(lang)),
        ("Format", lambda: format_check(lang)),
        ("Type Check", lambda: typecheck(lang)),
        ("Test", lambda: test(lang)),
        ("Security", lambda: security(lang)),
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
    parser = argparse.ArgumentParser(
        description="治理审计员 - 多语言支持",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
支持的语言: {", ".join(lang.value for lang in list_supported_languages())}

Actions:
  lint [--lang LANG]              运行 lint 检查
  format [--lang LANG]            运行 format 检查
  typecheck [--lang LANG]         运行类型检查
  test [--lang LANG]              运行测试套件
  security [--lang LANG]          运行安全扫描
  validate-governance-docs        验证治理文档
  check-ai-sdlc-compliance        检查 AI-SDLC 合规性
  audit-hallucination-risks       审计幻觉风险
  ai-quality-gate                 运行 AI 代码质量门禁
  full [--lang LANG]              运行完整审计
        """,
    )
    parser.add_argument("action", nargs="?", help="要执行的动作")
    parser.add_argument("--lang", help="逗号分隔的语言列表 (如: python,typescript)")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    action_map: dict[str, Callable[[], int]] = {
        "lint": lambda: 0 if lint(args.lang) else 1,
        "format": lambda: 0 if format_check(args.lang) else 1,
        "typecheck": lambda: 0 if typecheck(args.lang) else 1,
        "test": lambda: 0 if test(args.lang) else 1,
        "security": lambda: 0 if security(args.lang) else 1,
        "validate-governance-docs": lambda: 0 if validate_governance_docs() else 1,
        "check-ai-sdlc-compliance": lambda: 0 if check_ai_sdlc_compliance() else 1,
        "audit-hallucination-risks": lambda: 0 if audit_hallucination_risks() else 1,
        "ai-quality-gate": lambda: 0 if ai_quality_gate() else 1,
        "full": lambda: full(args.lang),
    }

    if args.action in action_map:
        sys.exit(action_map[args.action]())
    else:
        print(f"❌ 未知 action: {args.action}")
        print(f"可用 actions: {', '.join(action_map.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
