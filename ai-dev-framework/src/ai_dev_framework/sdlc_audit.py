"""
AI-SDLC 合规审计 — 检查项目是否遵循 AI-SDLC 流程

检测维度:
- 需求阶段: 是否有 PRD/需求文档
- 设计阶段: 是否有架构文档/ADR
- 实现阶段: 是否有测试、类型注解
- 审查阶段: 是否有 PR 模板、代码审查证据
- 部署阶段: 是否有 CI/CD 配置
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SDLCStage:
    """SDLC 阶段检查结果"""

    name: str
    passed: bool
    checks: list[dict] = field(default_factory=list)
    score: float = 0.0
    suggestions: list[str] = field(default_factory=list)


@dataclass
class SDLCAuditResult:
    """完整审计结果"""

    project: str
    timestamp: str = ""
    stages: list[SDLCStage] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.stages:
            self.overall_score = sum(s.score for s in self.stages) / len(self.stages)
            self.passed = all(s.passed for s in self.stages)


def _has_file(pattern: str, root: Path) -> bool:
    """检查目录中是否存在匹配 pattern 的文件"""
    return len([p for p in root.rglob(pattern) if p.is_file()]) > 0


def _has_content_pattern(pattern: str, root: Path, glob_pat: str = "*.md") -> bool:
    """检查目录中的文件是否包含匹配 pattern 的内容"""
    for p in root.rglob(glob_pat):
        if p.is_file():
            try:
                content = p.read_text("utf-8")
                if re.search(pattern, content, re.IGNORECASE):
                    return True
            except (OSError, UnicodeDecodeError):
                continue
    return False


def _count_type_annotations(root: Path) -> tuple[int, int]:
    """统计类型注解覆盖率"""
    typed = 0
    total = 0
    for p in root.rglob("*.py"):
        if p.is_file() and not any(part.startswith(".") for part in p.parts):
            try:
                content = p.read_text("utf-8")
                # 简单统计：带 -> 返回类型的函数
                typed += len(re.findall(r"def \w+\([^)]*\)\s*->", content))
                total += len(re.findall(r"def \w+\(", content))
            except (OSError, UnicodeDecodeError):
                continue
    return typed, total


def _count_test_files(root: Path) -> int:
    """统计测试文件数量"""
    count = 0
    for p in root.rglob("*"):
        if p.is_file():
            name = p.name
            if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".spec.ts"):
                count += 1
    return count


def audit_sdlc(project_path: str | Path) -> SDLCAuditResult:
    """对项目执行 AI-SDLC 合规审计"""
    root = Path(project_path)
    project_name = root.name
    stages: list[SDLCStage] = []

    # ── 需求阶段 ──
    req_checks = []
    req_score = 0.0

    has_prd = _has_file("*PRD*", root) or _has_file("*prd*", root)
    req_checks.append({"check": "PRD 文档", "passed": has_prd, "detail": "found" if has_prd else "not found"})
    if has_prd:
        req_score += 0.4

    has_requirements = _has_content_pattern("requirement|user story|功能需求", root, "*.md")
    req_checks.append(
        {"check": "需求描述", "passed": has_requirements, "detail": "found" if has_requirements else "not found"}
    )
    if has_requirements:
        req_score += 0.3

    has_readme = (root / "README.md").exists()
    req_checks.append({"check": "README", "passed": has_readme, "detail": "found" if has_readme else "not found"})
    if has_readme:
        req_score += 0.3

    req_suggestions = []
    if not has_prd:
        req_suggestions.append("创建 PRD 文档（docs/prd.md）描述项目目标和功能需求")
    if not has_requirements:
        req_suggestions.append("在文档中明确记录用户故事或功能需求")
    stages.append(
        SDLCStage(
            name="需求 (Requirements)",
            passed=req_score >= 0.7,
            checks=req_checks,
            score=req_score,
            suggestions=req_suggestions,
        )
    )

    # ── 设计阶段 ──
    des_checks = []
    des_score = 0.0

    has_adr = _has_file("ADR*", root) or _has_file("adr*", root) or (root / "docs/adr").is_dir()
    des_checks.append({"check": "架构决策记录 (ADR)", "passed": has_adr, "detail": "found" if has_adr else "not found"})
    if has_adr:
        des_score += 0.35

    has_arch_doc = _has_content_pattern("architecture|架构|design|设计", root, "*.md")
    des_checks.append(
        {"check": "架构/设计文档", "passed": has_arch_doc, "detail": "found" if has_arch_doc else "not found"}
    )
    if has_arch_doc:
        des_score += 0.35

    has_datamodel = _has_content_pattern("data model|数据模型|entity|实体|schema", root, "*.md")
    des_checks.append(
        {"check": "数据模型文档", "passed": has_datamodel, "detail": "found" if has_datamodel else "not found"}
    )
    if has_datamodel:
        des_score += 0.3

    des_suggestions = []
    if not has_adr:
        des_suggestions.append("创建 docs/adr/ 目录，记录架构决策")
    if not has_arch_doc:
        des_suggestions.append("编写架构概览文档（docs/architecture.md）")
    stages.append(
        SDLCStage(
            name="设计 (Design)",
            passed=des_score >= 0.7,
            checks=des_checks,
            score=des_score,
            suggestions=des_suggestions,
        )
    )

    # ── 实现阶段 ──
    imp_checks = []
    imp_score = 0.0

    typed, total = _count_type_annotations(root)
    type_ratio = typed / total if total > 0 else 0
    imp_checks.append(
        {"check": "类型注解覆盖率", "passed": type_ratio >= 0.6, "detail": f"{type_ratio:.0%} ({typed}/{total})"}
    )
    imp_score += min(0.35 * type_ratio * 1.67, 0.35)

    test_count = _count_test_files(root)
    has_tests = test_count > 0
    imp_checks.append(
        {"check": "测试文件", "passed": has_tests, "detail": f"{test_count} files found" if has_tests else "none found"}
    )
    if has_tests:
        imp_score += 0.35

    has_lint_config = (
        (root / "pyproject.toml").exists() or (root / ".ruff.toml").exists() or (root / ".eslintrc").exists()
    )
    imp_checks.append(
        {"check": "Linter 配置", "passed": has_lint_config, "detail": "found" if has_lint_config else "not found"}
    )
    if has_lint_config:
        imp_score += 0.15

    has_gitignore = (root / ".gitignore").exists()
    imp_checks.append(
        {"check": ".gitignore", "passed": has_gitignore, "detail": "found" if has_gitignore else "not found"}
    )
    if has_gitignore:
        imp_score += 0.15

    imp_suggestions = []
    if type_ratio < 0.6:
        imp_suggestions.append(f"增加类型注解: 当前覆盖率 {type_ratio:.0%}，建议达到 60%+")
    if not has_tests:
        imp_suggestions.append("添加测试文件（tests/ 目录）")
    if not has_lint_config:
        imp_suggestions.append("添加 linter 配置文件（pyproject.toml / .ruff.toml）")
    stages.append(
        SDLCStage(
            name="实现 (Implementation)",
            passed=imp_score >= 0.7,
            checks=imp_checks,
            score=imp_score,
            suggestions=imp_suggestions,
        )
    )

    # ── 审查阶段 ──
    rev_checks = []
    rev_score = 0.0

    has_pr_template = _has_file("PULL_REQUEST_TEMPLATE*", root / ".github") or _has_file(
        "pull_request_template*", root / ".github"
    )
    rev_checks.append(
        {"check": "PR 模板", "passed": has_pr_template, "detail": "found" if has_pr_template else "not found"}
    )
    if has_pr_template:
        rev_score += 0.35

    has_codeowners = (root / ".github" / "CODEOWNERS").exists()
    rev_checks.append(
        {"check": "CODEOWNERS", "passed": has_codeowners, "detail": "found" if has_codeowners else "not found"}
    )
    if has_codeowners:
        rev_score += 0.25

    has_review_guide = _has_content_pattern("review|code review|代码审查|PR review", root, "*.md")
    rev_checks.append(
        {"check": "代码审查指南", "passed": has_review_guide, "detail": "found" if has_review_guide else "not found"}
    )
    if has_review_guide:
        rev_score += 0.2

    has_contributing = (root / "CONTRIBUTING.md").exists()
    rev_checks.append(
        {"check": "CONTRIBUTING.md", "passed": has_contributing, "detail": "found" if has_contributing else "not found"}
    )
    if has_contributing:
        rev_score += 0.2

    rev_suggestions = []
    if not has_pr_template:
        rev_suggestions.append("创建 .github/PULL_REQUEST_TEMPLATE.md")
    if not has_codeowners:
        rev_suggestions.append("创建 .github/CODEOWNERS 指定代码审查者")
    if not has_contributing:
        rev_suggestions.append("创建 CONTRIBUTING.md 指导贡献流程")
    stages.append(
        SDLCStage(
            name="审查 (Review)",
            passed=rev_score >= 0.7,
            checks=rev_checks,
            score=rev_score,
            suggestions=rev_suggestions,
        )
    )

    # ── 部署阶段 ──
    dep_checks = []
    dep_score = 0.0

    has_ci = _has_file(".github/workflows/*.yml", root)
    dep_checks.append({"check": "CI 配置", "passed": has_ci, "detail": "found" if has_ci else "not found"})
    if has_ci:
        dep_score += 0.4

    has_dockerfile = (root / "Dockerfile").exists() or _has_file("Dockerfile*", root)
    dep_checks.append(
        {"check": "容器化", "passed": has_dockerfile, "detail": "found" if has_dockerfile else "not found"}
    )
    if has_dockerfile:
        dep_score += 0.3

    has_deploy_doc = _has_content_pattern("deploy|deployment|部署|release|发布", root, "*.md")
    dep_checks.append(
        {"check": "部署文档", "passed": has_deploy_doc, "detail": "found" if has_deploy_doc else "not found"}
    )
    if has_deploy_doc:
        dep_score += 0.3

    dep_suggestions = []
    if not has_ci:
        dep_suggestions.append("配置 CI（GitHub Actions）")
    if not has_dockerfile:
        dep_suggestions.append("添加 Dockerfile 支持容器化部署")
    if not has_deploy_doc:
        dep_suggestions.append("编写部署文档（docs/deploy.md）")
    stages.append(
        SDLCStage(
            name="部署 (Deploy)",
            passed=dep_score >= 0.7,
            checks=dep_checks,
            score=dep_score,
            suggestions=dep_suggestions,
        )
    )

    return SDLCAuditResult(project=project_name, stages=stages)


def print_audit(result: SDLCAuditResult, verbose: bool = False) -> int:
    """打印审计结果。返回 exit code (0=通过)。"""
    print(f"\n{'=' * 60}")
    print(f"  AI-SDLC 合规审计: {result.project}")
    print(f"  {result.timestamp}")
    print(f"{'=' * 60}\n")

    for stage in result.stages:
        icon = "✅" if stage.passed else "❌"
        print(f"  {icon} {stage.name} ({stage.score:.0%})")
        if verbose:
            for check in stage.checks:
                c_icon = "✅" if check["passed"] else "❌"
                print(f"      {c_icon} {check['check']}: {check['detail']}")
            if stage.suggestions:
                for s in stage.suggestions:
                    print(f"      💡 {s}")
        print()

    print(f"  总体评分: {result.overall_score:.0%}")
    print(f"  状态: {'✅ 全部通过' if result.passed else '❌ 需改进'}")
    print()

    if not result.passed:
        print("  改进建议:")
        for stage in result.stages:
            if not stage.passed:
                for s in stage.suggestions:
                    print(f"    • [{stage.name}] {s}")
        print()

    return 0 if result.passed else 1
