#!/usr/bin/env python3
"""
Case Study Validation Script

Validates case study submissions for quality and completeness.
Used in CI/CD and local pre-submission checks.

Usage:
    python validate_case_study.py --path case-studies/my-case/
    python validate_case_study.py --path case-studies/my-case/ --strict
    python validate_case_study.py --all  # Validate all cases
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:  # python -m tools.scripts.validate_case_study (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/validate_case_study.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

from tools.scripts._case_study_common import (  # noqa: E402
    extract_insights_section,
    extract_numbered_insights,
    extract_table_rows,
    has_efficiency_table,
    parse_efficiency_values,
)
from tools.scripts._paths import resolve_repo_path  # noqa: E402


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationResult:
    severity: Severity
    message: str
    file: str = ""
    line: int = 0


class CaseStudyValidator:
    """Validates case study structure and content quality."""

    # Support both old and new section headers - more flexible matching
    REQUIRED_SECTIONS_ALT = {
        "背景与挑战": [
            "## 背景与挑战",
            "## 项目背景",
            "## 项目背景与挑战",
            "## 背景",
            "## 📋 场景背景",
            "## 场景背景",
            "## 📋 场景背景",
        ],
        "AI 协作过程": [
            "## AI 协作过程",
            "## 1. 需求阶段",
            "## 需求阶段",
            "## 1. 需求阶段",
            "## 1. 需求阶段",
            "## ⚡ AI 协作过程",
            "## 过程",
            "## AI 协作流程",
        ],
        "效率对比数据": [
            "## 效率对比数据",
            "## 效率提升分析",
            "## 效率对比",
            "## 效率对比表",
            "## 📈 效率提升",
            "## 效率提升",
            "## 对比",
            "## 📈 效率提升",
        ],
        "关键洞察": [
            "## 关键洞察",
            "## 关键洞察与反思",
            "## 关键洞察与总结",
            "## 💡 关键洞察",
            "## 关键技术决策",
            "## 洞察",
            "## 💡 关键洞察",
        ],
        "适用场景": [
            "## 适用场景",
            "## 适用场景与建议",
            "## 🎯 适用场景",
            "## 适用场景",
        ],
        "交付物清单": ["## 交付物清单", "## 交付物", "## 交付清单"],
        "提交前检查": ["## 提交前检查", "## 提交清单", "## ✅ 提交前检查"],
    }

    # Legacy sections (old format - warn only, don't error)
    LEGACY_SECTIONS = {
        "项目背景": ["## 项目背景", "## 背景"],
        "需求阶段": ["## 1. 需求阶段", "## 需求阶段"],
        "设计阶段": ["## 2. 设计阶段", "## 设计阶段"],
        "实现阶段": ["## 3. 实现阶段", "## 编码阶段", "## 实现阶段"],
        "优化交付": ["## 4. 优化阶段", "## 优化阶段", "## 交付阶段"],
    }

    REQUIRED_TABLES = [
        "效率对比数据",
        "交付物清单",
    ]

    PHASE_KEYWORDS = [
        "阶段 1",
        "阶段 2",
        "阶段 3",
        "阶段 4",
        "需求",
        "架构",
        "编码",
        "优化",
        "1. 需求",
        "2. 设计",
        "3. 实现",
        "4. 优化",
        "Phase 1",
        "Phase 2",
        "Phase 3",
        "Phase 4",
        "AI 协作",
        "人",
        "AI",
    ]

    def __init__(self, strict: bool = False, legacy_mode: bool = False) -> None:
        self.strict = strict
        self.legacy_mode = legacy_mode
        self.results: list[ValidationResult] = []

    def validate(self, case_path: Path) -> list[ValidationResult]:
        """Run all validation checks on a case study."""
        self.results = []

        # Support both flat .md and directory with README.md
        readme_path = case_path
        if case_path.is_dir():
            readme_path = case_path / "README.md"

        if not readme_path.exists():
            self._add_error("Missing README.md or case study file", str(case_path))
            return self.results

        content = readme_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        self._check_sections(content)
        self._check_tables(content)
        self._check_phases(content)
        self._check_efficiency_table(content)
        self._check_insights(content)
        self._check_applicability(content)
        self._check_deliverables(content)
        self._check_submission_checklist(content)
        self._check_format(lines)
        self._check_links(case_path, content)

        return self.results

    def _check_sections(self, content: str) -> None:
        """Verify all required sections exist (V2.21 P5-18 拆分: 抽 _has_legacy_section + _report_legacy_or_missing)."""
        for section_name, alt_headers in self.REQUIRED_SECTIONS_ALT.items():
            found = any(alt in content for alt in alt_headers)
            if found:
                continue
            self._report_legacy_or_missing(content, section_name, alt_headers)

    def _has_legacy_section(self, content: str) -> bool:
        """检查 LEGACY_SECTIONS 中是否任一 alt 在 content 中 (模块级 helper).

        Args:
            content: 文档内容

        Returns:
            是否存在 legacy section
        """
        for legacy_headers in self.LEGACY_SECTIONS.values():
            for legacy_alt in legacy_headers:
                if legacy_alt in content:
                    return True
        return False

    def _report_legacy_or_missing(self, content: str, section_name: str, alt_headers: list[str]) -> None:
        """根据 legacy 检测结果报告 error/warning (模块级 helper).

        Args:
            content: 文档内容
            section_name: 当前必填 section 名
            alt_headers: 候选 alt headers
        """
        if self._has_legacy_section(content):
            msg = f"Using legacy section format: {section_name} (consider updating to new format)"
            if self.strict:
                self._add_error(msg)
            else:
                self._add_warning(msg)
        else:
            self._add_error(f"Missing required section: {section_name} (tried: {', '.join(alt_headers)})")

    def _check_tables(self, content: str) -> None:
        """Verify required tables exist."""
        for table in self.REQUIRED_TABLES:
            if table not in content:
                self._add_new_submission_warning(
                    f"Missing recommended table: {table} (required for new submissions)",
                    "README.md",
                )

    def _check_phases(self, content: str) -> None:
        """Verify AI collaboration phases are documented."""
        found_phases = 0
        for kw in self.PHASE_KEYWORDS:
            if kw in content:
                found_phases += 1

        if found_phases < 3:
            self._add_warning(
                f"Only {found_phases}/8 phase keywords found. Consider documenting all 4 phases explicitly.",
                "README.md",
            )

        # Check for AI/Person role separation - more flexible
        role_indicators = [
            "人",
            "AI",
            "Human",
            "human",
            "人工",
            "人类",
            "协作",
            "角色",
            "Role",
            "role",
        ]
        has_role_separation = any(indicator in content for indicator in role_indicators)

        if not has_role_separation:
            self._add_warning(
                "No clear role separation in collaboration process. Consider documenting what human did vs what AI did.",
                "README.md",
            )

    def _check_efficiency_table(self, content: str) -> None:
        """Validate efficiency comparison table."""
        if not self._has_efficiency_table(content):
            self._add_new_submission_warning(
                "Missing efficiency comparison table with required columns (required for new submissions)",
                "README.md",
            )
            return

        data_rows = self._extract_table_rows(content)
        if not data_rows:
            self._add_error("Efficiency table found but no data rows")
            return

        self._validate_table_rows(data_rows)

    def _has_efficiency_table(self, content: str) -> bool:
        """Check if content has an efficiency table."""
        return has_efficiency_table(content)

    def _extract_table_rows(self, content: str) -> list[str]:
        """Extract table data rows from content."""
        return extract_table_rows(content)

    def _validate_table_rows(self, data_rows: list[str]) -> None:
        """Validate table data rows."""
        for row in data_rows:
            if row.strip() in ["|---|", "| --- |", "|:---|"]:
                continue
            cols = [c.strip() for c in row.split("|")[1:-1]]
            if len(cols) >= 4:
                stage, traditional, ai, boost = cols[:4]
                if stage in ["总计", "总计 "] or "总计" in stage:
                    self._validate_boost_calculation(traditional, ai, boost)

    def _validate_boost_calculation(self, traditional: str, ai: str, boost: str) -> None:
        """Validate that boost = traditional / ai (in hours)."""
        try:
            parsed = self._parse_efficiency_values(traditional, ai, boost)
            if parsed:
                t_hours, a_hours, boost_val = parsed
                self._check_boost_accuracy(traditional, ai, t_hours, a_hours, boost_val)
        except (ValueError, AttributeError):
            self._add_warning(
                f"Could not parse efficiency values: {traditional} / {ai} → {boost}",
                "README.md",
            )

    def _parse_efficiency_values(self, traditional: str, ai: str, boost: str) -> tuple[float, float, float] | None:
        """Parse efficiency values from table cells."""
        return parse_efficiency_values(traditional, ai, boost)

    def _check_boost_accuracy(
        self,
        traditional: str,
        ai: str,
        t_hours: float,
        a_hours: float,
        boost_val: float,
    ) -> None:
        """Check if calculated boost matches claimed boost."""
        expected = t_hours / a_hours
        if abs(expected - boost_val) > 0.5:
            self._add_warning(
                f"Boost calculation may be off: {traditional} / {ai} = {expected:.1f}x, claimed {boost_val}x",
                "README.md",
            )

    def _check_insights(self, content: str) -> None:
        """Validate key insights quality."""
        insights_text = self._extract_insights_section(content)
        if not insights_text:
            self._add_new_submission_warning("Missing insights section (required for new submissions)", "README.md")
            return

        numbered = self._extract_numbered_insights(insights_text)
        if len(numbered) < 3:
            self._add_warning(
                f"Only {len(numbered)} numbered insights found. Recommend 3-5.",
                "README.md",
            )

        self._check_insights_specificity(insights_text)

    def _extract_insights_section(self, content: str) -> str:
        """Extract insights section from content."""
        return extract_insights_section(content)

    def _extract_numbered_insights(self, insights_text: str) -> list[str]:
        """Extract numbered insights from text."""
        return extract_numbered_insights(insights_text)

    def _check_insights_specificity(self, insights_text: str) -> None:
        """Check insights for specificity."""
        vague_terms = ["很快", "很高", "很大", "很多", "很强", "很方便", "很高效"]
        for term in vague_terms:
            if term in insights_text.lower() and "具体" not in insights_text.lower():
                self._add_warning(
                    f"Insights may be vague (contains '{term}'). Use specific numbers/patterns.",
                    "README.md",
                )
                break

    def _check_applicability(self, content: str) -> None:
        """Check applicability scenarios are marked."""
        if "适用场景" not in content:
            self._add_new_submission_warning("Missing 适用场景 section (required for new submissions)", "README.md")
            return

        # Check for checkboxes
        if "- [ ]" not in content and "- [x]" not in content:
            self._add_warning(
                "Applicability scenarios should use checkbox format (- [ ] / - [x])",
                "README.md",
            )

    def _check_deliverables(self, content: str) -> None:
        """Check deliverables checklist."""
        if "交付物清单" not in content:
            self._add_new_submission_warning("Missing 交付物清单 section (required for new submissions)", "README.md")
            return

        required_deliverables = [
            "PRD",
            "DESIGN",
            "代码",
            "测试",
            "数据",
            "洞察",
            "场景",
        ]
        missing = []
        for d in required_deliverables:
            if d not in content:
                missing.append(d)

        if missing:
            self._add_new_submission_warning(f"Missing deliverable checkboxes: {', '.join(missing)}", "README.md")

    def _check_submission_checklist(self, content: str) -> None:
        """Check submission checklist."""
        if "提交前检查" not in content:
            self._add_new_submission_warning("Missing 提交前检查 section", "README.md")

        required_checks = [
            "标题格式",
            "Label",
            "必填章节",
            "效率数据",
            "关键洞察",
            "代码/文档链接",
        ]
        missing = []
        for c in required_checks:
            if c not in content:
                missing.append(c)

        if missing:
            self._add_new_submission_warning(f"Submission checklist incomplete: {', '.join(missing)}", "README.md")

    def _check_format(self, lines: list[str]) -> None:
        """Check markdown formatting."""
        for i, line in enumerate(lines, 1):
            # Check for table alignment
            if "|" in line and "---" in line:
                # Header separator row
                if not re.match(r"^\|[\s\-\:|]+\|$", line):
                    self._add_warning(f"Table separator misaligned at line {i}", "README.md", i)

            # Check for unescaped pipes in code blocks
            if "```" in line:
                pass  # Skip inside code blocks

            # Check for trailing whitespace
            if line.endswith("  ") or line.endswith("\t"):
                self._add_warning(f"Trailing whitespace at line {i}", "README.md", i)

    def _check_links(self, case_path: Path, content: str) -> None:
        """Check wikilinks and external links."""
        # Check wikilinks
        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
        for link in wikilinks:
            # Check if target exists
            if "|" in link:
                target = link.split("|")[0].strip()
            else:
                target = link.strip()

            if target.startswith("docs/") or target.startswith("case-studies/") or target.startswith("examples/"):
                target_path = resolve_repo_path(target)
                if not target_path.exists():
                    # Try with .md extension
                    if not (target_path.with_suffix(".md")).exists():
                        self._add_warning(f"Broken wikilink: [[{link}]] -> {target_path}", "README.md")

    def _add_error(self, msg: str, file: str = "", line: int = 0) -> None:
        self.results.append(ValidationResult(Severity.ERROR, msg, file, line))

    def _add_warning(self, msg: str, file: str = "", line: int = 0) -> None:
        if self.strict:
            self._add_error(msg, file, line)
        else:
            self.results.append(ValidationResult(Severity.WARNING, msg, file, line))

    def _add_new_submission_warning(self, msg: str, file: str = "", line: int = 0) -> None:
        """报告"新提交要求"类问题。

        这类要求只针对新提交的案例。存量案例早于该要求出台，批量校验不应
        因为缺少新格式而失败，因此 legacy_mode 下不因 --strict 升级为 error。
        """
        if self.strict and not self.legacy_mode:
            self._add_error(msg, file, line)
        else:
            self.results.append(ValidationResult(Severity.WARNING, msg, file, line))


def print_results(results: list[ValidationResult], case_name: str = "") -> None:
    """Pretty print validation results (V2.21 P5-17 拆分: 抽 _partition_by_severity + _print_severity_section)."""
    if case_name:
        print(f"\n{'=' * 60}")
        print(f"  📋 Validation: {case_name}")
        print(f"{'=' * 60}")

    errors, warnings = _partition_by_severity(results)
    if not errors and not warnings:
        print("  ✅ All checks passed!")
        return

    _print_severity_section("❌", "Error(s)", errors)
    _print_severity_section("⚠️ ", "Warning(s)", warnings)
    print()


def _partition_by_severity(results: list[ValidationResult]) -> tuple[list[ValidationResult], list[ValidationResult]]:
    """按严重度二分: errors / warnings (模块级 helper).

    Args:
        results: 校验结果列表

    Returns:
        (errors, warnings) 元组
    """
    errors = [r for r in results if r.severity == Severity.ERROR]
    warnings = [r for r in results if r.severity == Severity.WARNING]
    return errors, warnings


def _print_severity_section(icon: str, label: str, items: list[ValidationResult]) -> None:
    """打印单个严重度段 (模块级 helper).

    Args:
        icon: 段落图标 (❌ / ⚠️)
        label: 段落标签 (Error(s) / Warning(s))
        items: 该严重度的 result 列表
    """
    if not items:
        return
    print(f"\n  {icon} {len(items)} {label}:")
    for item in items:
        loc = f" ({item.file}:{item.line})" if item.file else ""
        print(f"  {loc}  {item.message}")


def _discover_case_studies(base: Path) -> list[Path]:
    """Discover case study items in the base directory."""
    return sorted([d for d in base.iterdir() if not d.name.startswith(".") and (d.is_dir() or d.suffix == ".md")])


def _validate_all_cases(case_items: list[Path], strict: bool) -> bool:
    """Validate all case studies. Returns True if all passed.

    legacy_mode=True: "新提交要求"类问题（效率对比表、交付物清单、提交前检查）
    不因 --strict 升级为 error。存量案例早于该要求出台，批量扫描不应因缺少
    新格式而失败；提交前校验请用 --path <案例> --strict。
    """
    all_passed = True
    for case_item in case_items:
        validator = CaseStudyValidator(strict=strict, legacy_mode=True)
        results = validator.validate(case_item)
        print_results(results, case_item.name)

        if any(r.severity == Severity.ERROR for r in results):
            all_passed = False

    return all_passed


def _validate_single_case(case_path: Path, strict: bool, json_output: bool) -> int:
    """Validate a single case study. Returns exit code."""
    if not case_path.exists():
        print(f"Error: Path not found: {case_path}")
        return 1

    validator = CaseStudyValidator(strict=strict)
    results = validator.validate(case_path)
    print_results(results, case_path.name)

    if json_output:
        print(
            json.dumps(
                [
                    {
                        "severity": r.severity.value,
                        "message": r.message,
                        "file": r.file,
                        "line": r.line,
                    }
                    for r in results
                ],
                ensure_ascii=False,
                indent=2,
            )
        )

    return 0 if not any(r.severity == Severity.ERROR for r in results) else 1


def _adg_scan(changed_files_str: str) -> int:
    """Scan code snippets in changed files using ADG."""
    import json
    import os
    import pathlib
    import re
    import subprocess
    import tempfile

    changed_files = [f for f in changed_files_str.split() if f and os.path.exists(f)]
    for file in changed_files:
        print(f"ADG scanning code snippets in: {file}")
        with open(file) as f:
            content = f.read()
        # Find all fenced code blocks with language hints
        blocks = re.findall(r"```(\w+)\n(.*?)\n```", content, re.DOTALL)
        for lang, code in blocks:
            # lang_map = {  # 用于未来扩展
            #     "py": "python",
            #     "python": "python",
            #     "js": "javascript",
            #     "javascript": "javascript",
            #     "ts": "typescript",
            #     "typescript": "typescript",
            #     "go": "go",
            #     "rust": "rust",
            #     "rs": "rust",
            # }
            with tempfile.NamedTemporaryFile(suffix=f".{lang}", mode="w", delete=False) as f:  # type: ignore[assignment]
                f.write(code)
                tmp = f.name
            r = subprocess.run(
                ["adg", "check", tmp, "--severity", "error", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 1:
                result = json.loads(r.stdout)
                issues = result.get("issues", [])
                errors = [i for i in issues if i["severity"] == "error"]
                if errors:
                    print(
                        f"::warning file={file}::Found {len(errors)} error(s) in code block ({lang}): {errors[0]['message']}"
                    )
            pathlib.Path(tmp).unlink()
    return 0


def _auth_check(changed_files_str: str) -> int:
    """Check authenticity markers in changed files."""
    import os
    import re

    changed_files = [f for f in changed_files_str.split() if f and os.path.exists(f)]
    for filepath in changed_files:
        print(f"=== Checking authenticity: {filepath} ===")
        content = Path(filepath).read_text(encoding="utf-8")
        checks = [
            ("GitHub repo link", r"github\.com/[\w-]+/[\w-]+"),
            ("PR link", r"github\.com/[\w-]+/[\w-]+/pull/\d+"),
            ("Commit hash", r"[0-9a-f]{7,40}"),
            ("Efficiency data", r"效率提升|提升.*x|\d+x"),
        ]
        for name, pattern in checks:
            found = bool(re.search(pattern, content))
            status = "OK" if found else "MISSING"
            print(f"  {status} {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate case study submissions")
    parser.add_argument("--path", type=str, help="Path to single case study directory")
    parser.add_argument("--all", action="store_true", help="Validate all cases in docs/case-studies/")
    parser.add_argument("--base", type=str, help="Base directory for --all (default: <repo>/docs/case-studies)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--adg-scan", type=str, help="Scan code snippets in changed files")
    parser.add_argument("--auth-check", type=str, help="Check authenticity markers in changed files")
    args = parser.parse_args()

    base = resolve_repo_path(args.base) if args.base else resolve_repo_path("docs/case-studies")

    if args.adg_scan:
        return _adg_scan(args.adg_scan)
    elif args.auth_check:
        return _auth_check(args.auth_check)
    elif args.all:
        if not base.is_dir():
            print(f"No case studies directory found at {base}/")
            return 1
        case_items = _discover_case_studies(base)
        if not case_items:
            print(f"No case studies found in {base}/")
            return 1

        all_passed = _validate_all_cases(case_items, args.strict)
        return 0 if all_passed else 1

    elif args.path:
        case_path = Path(args.path)
        return _validate_single_case(case_path, args.strict, args.json)

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
