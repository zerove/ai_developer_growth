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
from typing import NamedTuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.scripts._common import (  # noqa: E402
    get_project_root,
    print_check,
    print_section,
    run_command,
)
from tools.scripts.language_registry import (  # noqa: E402
    EXTENSION_MAP,
    Language,
    ToolCategory,
    detect_language,
    get_tool,
    list_supported_languages,
)

# ── 治理层文档清单由 tools/scripts/_common.py 统一提供 (唯一真源) ──


class UnsafePattern(NamedTuple):
    """不安全模式定义: 正则, 描述, 排除文件列表, 排除正则"""

    pattern: str
    desc: str
    exclude_files: list[str]
    exclude_pattern: str | None = None


UNSAFE_PATTERNS: list[UnsafePattern] = [
    UnsafePattern(
        pattern=r"eval\(",
        desc="eval 调用 - 代码注入风险",
        exclude_files=[
            "auto_fix.py",
            "generate_fixes.py",
            "ai_quality_gate.py",
            "rule_editor.py",
            "hallucination_detector.py",
            "fix_heuristics.py",
        ],
    ),
    UnsafePattern(
        pattern=r"exec\(",
        desc="exec 调用 - 代码注入风险",
        exclude_files=[
            "auto_fix.py",
            "generate_fixes.py",
            "ai_quality_gate.py",
            "rule_editor.py",
            "hallucination_detector.py",
            "fix_heuristics.py",
        ],
    ),
    UnsafePattern(
        pattern=r"os\.system\(",
        desc="os.system() - 应使用 subprocess",
        exclude_files=[
            "generate_fixes.py",
            "hallucination_detector.py",
            "fix_heuristics.py",
            "auto_fix.py",
        ],
    ),
    UnsafePattern(
        pattern=r"pickle\.loads?\(",
        desc="pickle - 反序列化风险",
        exclude_files=["generate_fixes.py", "hallucination_detector.py"],
    ),
    UnsafePattern(
        pattern=r"yaml\.load\((?!.*Loader)",
        desc="yaml.load 不安全 - 应使用 safe_load",
        # 早前这里同时设了 exclude_pattern=r"yaml\.load\((?!.*Loader)"，与 pattern
        # 完全相同。_check_unsafe_patterns 先判 exclude 再判 pattern，两者相同
        # 导致排除永远先命中并 continue —— 这条规则从此永不触发（死规则），
        # 恰好掩盖了它本该检出的不安全反序列化。改为只靠 exclude_files 排除
        # 规则定义文件里描述该模式的字符串字面量。
        exclude_files=["generate_fixes.py", "hallucination_detector.py", "auto_fix.py"],
    ),
]


def _check_unsafe_patterns(content: str, patterns: list[UnsafePattern], filepath: str = "") -> list[str]:
    """检查不安全模式，支持排除文件和排除模式"""
    risks = []
    filename = Path(filepath).name if filepath else ""
    for item in patterns:
        if filename in item.exclude_files:
            continue

        if item.exclude_pattern and re.search(item.exclude_pattern, content):
            continue

        if re.search(item.pattern, content):
            risks.append(item.desc)
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
                from tools.scripts.language_registry import LANGUAGE_ALIASES

                if part.lower() in LANGUAGE_ALIASES:
                    languages.append(LANGUAGE_ALIASES[part.lower()])
                else:
                    print(f"  ⚠️  未知语言: {part}，跳过")
    return languages


def _detect_project_languages(project_root: Path) -> list[Language]:
    """检测项目中使用的所有语言"""
    languages: list[Language] = []

    # Node 生态语言需要 package.json 作为工程化标志；
    # 否则散落的 .ts/.js（如编辑器扩展、构建产物）会因缺少
    # eslint/prettier/tsc 工具链而误报失败
    _node_ecosystem_languages = {Language.TYPESCRIPT, Language.JAVASCRIPT}
    has_package_json = (project_root / "package.json").exists()

    # 1. 通过配置文件检测主要语言
    main_lang = detect_language(project_root)
    if main_lang and not (main_lang in _node_ecosystem_languages and not has_package_json):
        languages.append(main_lang)

    # 2. 扫描所有扩展名，统计语言分布
    ext_counts = _count_language_extensions(project_root, _node_ecosystem_languages, has_package_json)

    # 按文件数排序，仅纳入占比显著的语言：
    # 示例脚本、编辑器扩展等附带文件不应触发全量工具链门禁
    total = sum(ext_counts.values())
    for lang in sorted(ext_counts, key=lambda k: ext_counts.get(k, 0), reverse=True)[:3]:
        if lang in languages:
            continue
        count = ext_counts.get(lang, 0)
        if count >= 50 or (total > 0 and count / total >= 0.2):
            languages.append(lang)

    return languages


def _count_language_extensions(
    project_root: Path,
    node_ecosystem_languages: set[Language],
    has_package_json: bool,
) -> dict[Language, int]:
    """扫描所有扩展名，统计语言分布。

    排除虚拟环境、依赖与构建产物目录，
    避免把第三方库文件误判为项目语言（如 .venv 中 lxml 的 .h 头文件）。
    Node 生态语言在缺少 package.json 时跳过（无工程化标志）。
    """
    _excluded_dirs = {
        ".venv",
        "venv",
        "node_modules",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "site-packages",
        "dist",
        "build",
        "target",
        "site",
    }
    ext_counts: dict[Language, int] = {}
    for ext, lang in EXTENSION_MAP.items():
        if lang in node_ecosystem_languages and not has_package_json:
            continue
        count = sum(1 for p in project_root.rglob(f"*{ext}") if not (set(p.parts) & _excluded_dirs))
        if count > 0:
            ext_counts[lang] = ext_counts.get(lang, 0) + count
    return ext_counts


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


def _make_language_check(
    name: str, section: str, category: ToolCategory, check_only: bool = False
) -> Callable[[str | None], bool]:
    """工厂化语言检查函数 (lint/format/typecheck/test/security 共用逻辑)。"""

    def run(lang: str | None = None) -> bool:
        print_section(section)
        root = get_project_root()

        if lang:
            languages = _parse_languages(lang)
        else:
            languages = _detect_project_languages(root)

        if not languages:
            print("⚠️  未检测到支持的语言，默认使用 Python")
            languages = [Language.PYTHON]

        passed, output = _run_check_for_languages(languages, category, root, check_only=check_only)
        print_check(name, passed, output)
        return passed

    return run


lint = _make_language_check("lint", "Lint 检查", ToolCategory.LINT, check_only=True)
format_check = _make_language_check("format", "Format 检查", ToolCategory.FORMAT, check_only=True)
typecheck = _make_language_check("typecheck", "类型检查", ToolCategory.TYPECHECK)
test = _make_language_check("test", "测试套件", ToolCategory.TEST)
security = _make_language_check("security", "安全扫描", ToolCategory.SECURITY)


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
    risks = _scan_unsafe_code_risks() + _scan_doc_absolute_claims()

    passed = len(risks) == 0
    print_check(f"幻觉风险 ({len(risks)} 个)", passed)
    if risks:
        for risk in risks[:20]:
            print(f"  - {risk}")
        if len(risks) > 20:
            print(f"  ... 还有 {len(risks) - 20} 个风险")
    return passed


def _scan_unsafe_code_risks() -> list[str]:
    """扫描 tools/scripts 下的不安全代码模式（排除工具定义文件）"""
    risks: list[str] = []
    root = get_project_root()
    for py_file in (root / "tools" / "scripts").rglob("*.py"):
        if py_file.name in _EXCLUDE_FROM_UNSAFE_AUDIT:
            continue
        content = py_file.read_text(encoding="utf-8")
        file_risks = _check_unsafe_patterns(content, UNSAFE_PATTERNS, py_file.name)
        for risk in file_risks:
            rel = py_file.relative_to(root)
            risks.append(f"{rel}: {risk}")
    return risks


def _scan_doc_absolute_claims() -> list[str]:
    """扫描 docs/efficiency 下的文档绝对化声明"""
    abs_patterns = [
        (r"永远\s*100%", "永远100%"),
        (r"绝对\s*100%", "绝对100%"),
        (r"保证\s*100%", "保证100%"),
        (r"从不\s*100%", "从不100%"),
        (r"永远", "永远"),
        (r"绝对(?!化)", "绝对"),
        (r"从不", "从不"),
    ]
    risks: list[str] = []
    root = get_project_root()
    for md_file in (root / "docs" / "efficiency").rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.split("\n"), 1):
            if _is_doc_skippable_line(line):
                continue
            rel = md_file.relative_to(root)
            risks.extend(
                f"{rel}:{line_num}: 绝对化声明 '{desc}'" for desc in _match_doc_absolute_claims(line, abs_patterns)
            )
    return risks


def _is_doc_skippable_line(line: str) -> bool:
    """是否跳过标题/代码块/表格/箭头行"""
    stripped = line.strip()
    return (
        stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("|") or stripped.startswith("←")
    )


def _match_doc_absolute_claims(line: str, abs_patterns: list[tuple[str, str]]) -> list[str]:
    """返回行内命中的绝对化声明描述（含例外/除非的声明不报告）"""
    matches = []
    for pat, desc in abs_patterns:
        if re.search(pat, line) and "例外" not in line and "除非" not in line:
            matches.append(desc)
    return matches


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
        "-m",
        "tools.scripts.ai_quality_gate",
        "--check-annotation",
        "--check-security",
        "--check-patterns",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=root)
    passed = result.returncode == 0
    print_check("人工智能质量门禁", passed, result.stdout + result.stderr)
    return passed


def full(lang: str | None = None) -> int:
    """运行完整治理审计 - 并行化执行无依赖检查"""
    from concurrent.futures import ThreadPoolExecutor

    print_section("🚀 完整治理审计 (v3.1 - 并行化)")

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
    with ThreadPoolExecutor(max_workers=min(len(checks), 4)) as executor:
        name_to_future = {name: executor.submit(func) for name, func in checks}
        for name, _ in checks:
            future = name_to_future[name]
            try:
                if not future.result():
                    failed.append(name)
            except Exception as e:
                failed.append(f"{name} (异常: {e})")

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


# Files to exclude from unsafe pattern audit (tool definition files, not user code)
_EXCLUDE_FROM_UNSAFE_AUDIT = {
    "auto_fix.py",
    "fix_heuristics.py",
    "generate_fixes.py",
    "hallucination_detector.py",
    "ide_rules_sync.py",
}
if __name__ == "__main__":
    main()
