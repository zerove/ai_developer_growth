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

    # Support both old and new section headers
    REQUIRED_SECTIONS_ALT = {
        "背景与挑战": ["## 背景与挑战", "## 项目背景", "## 项目背景与挑战", "## 背景"],
        "AI 协作过程": ["## AI 协作过程", "## 1. 需求阶段", "## 需求阶段", "## 1. 需求阶段", "## 1. 需求阶段"],
        "效率对比数据": ["## 效率对比数据", "## 效率提升分析", "## 效率对比", "## 效率对比表"],
        "关键洞察": ["## 关键洞察", "## 关键洞察与反思", "## 关键洞察与总结"],
        "适用场景": ["## 适用场景", "## 适用场景与建议"],
        "交付物清单": ["## 交付物清单", "## 交付物"],
        "提交前检查": ["## 提交前检查", "## 提交清单"],
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
        """Verify all required sections exist (supports alt headers)."""
        for section_name, alt_headers in self.REQUIRED_SECTIONS_ALT.items():
            found = False
            for alt in alt_headers:
                if alt in content:
                    found = True
                    break
            if not found:
                # Check legacy sections as fallback - but only for corresponding legacy section
                legacy_found = False
                # Find the corresponding legacy section name
                for legacy_name, legacy_headers in self.LEGACY_SECTIONS.items():
                    for legacy_alt in legacy_headers:
                        if legacy_alt in content:
                            legacy_found = True
                            break
                    if legacy_found:
                        break

                if legacy_found:
                    if self.strict:
                        self._add_error(
                            f"Using legacy section format: {section_name} (consider updating to new format)"
                        )
                    else:
                        self._add_warning(
                            f"Using legacy section format: {section_name} (consider updating to new format)"
                        )
                else:
                    self._add_error(f"Missing required section: {section_name} (tried: {', '.join(alt_headers)})")

    def _check_tables(self, content: str) -> None:
        """Verify required tables exist."""
        for table in self.REQUIRED_TABLES:
            if table not in content:
                self._add_warning(f"Missing recommended table: {table} (required for new submissions)", "README.md")

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

        # Check for AI/Person role separation
        if "人" not in content or "AI" not in content:
            self._add_warning(
                "No clear 人/AI role separation in collaboration process. Record what human did vs what AI did.",
                "README.md",
            )

    def _check_efficiency_table(self, content: str) -> None:
        """Validate efficiency comparison table."""
        # Find the efficiency table
        table_pattern = r"\|.*阶段.*\|.*传统.*\|.*AI.*\|.*提升.*\|"
        if not re.search(table_pattern, content):
            self._add_warning(
                "Missing efficiency comparison table with required columns (required for new submissions)", "README.md"
            )
            return

        # Extract table rows
        lines = content.split("\n")
        in_table = False
        data_rows = []

        for line in lines:
            if "|" in line and ("阶段" in line or "总计" in line):
                in_table = True
            if in_table and line.strip().startswith("|"):
                data_rows.append(line)
            elif in_table and not line.strip().startswith("|"):
                break

        if not data_rows:
            self._add_error("Efficiency table found but no data rows")
            return

        # Parse and validate
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
            # Extract numbers
            t_match = re.search(r"([\d.]+)\s*小时", traditional)

            # AI time could be in hours or minutes
            a_match_hours = re.search(r"([\d.]+)\s*小时", ai)
            a_match_minutes = re.search(r"([\d.]+)\s*分钟", ai)
            b_match = re.search(r"([\d.]+)x", boost)

            if t_match and b_match and (a_match_hours or a_match_minutes):
                t_hours = float(t_match.group(1))

                if a_match_hours:
                    a_hours = float(a_match_hours.group(1))
                else:
                    assert a_match_minutes is not None
                    a_hours = float(a_match_minutes.group(1)) / 60

                boost_val = float(b_match.group(1))

                expected = t_hours / a_hours
                if abs(expected - boost_val) > 0.5:  # Allow 0.5x tolerance
                    self._add_warning(
                        f"Boost calculation may be off: {traditional} / {ai} = {expected:.1f}x, claimed {boost_val}x",
                        "README.md",
                    )
        except (ValueError, AttributeError):
            self._add_warning(f"Could not parse efficiency values: {traditional} / {ai} → {boost}", "README.md")

    def _check_insights(self, content: str) -> None:
        """Validate key insights quality."""
        insight_section = content.split("## 关键洞察")
        if len(insight_section) < 2:
            return

        insights_text = insight_section[1]
        # Count numbered insights
        numbered = re.findall(r"^\d+\.\s+\*\*(洞察\s*\d+)?\*?\*\s*:?\s*(.+)$", insights_text, re.MULTILINE)
        if len(numbered) < 3:
            self._add_warning(f"Only {len(numbered)} numbered insights found. Recommend 3-5.", "README.md")

        # Check for specificity
        vague_terms = ["很快", "很高", "很大", "很多", "很强", "很方便", "很高效", "提升"]
        for term in vague_terms:
            if term in insights_text.lower() and "具体" not in insights_text.lower():
                self._add_warning(
                    f"Insights may be vague (contains '{term}'). Use specific numbers/patterns.", "README.md"
                )
                break

    def _check_applicability(self, content: str) -> None:
        """Check applicability scenarios are marked."""
        if "适用场景" not in content:
            self._add_warning("Missing 适用场景 section (required for new submissions)", "README.md")
            return

        # Check for checkboxes
        if "- [ ]" not in content and "- [x]" not in content:
            self._add_warning("Applicability scenarios should use checkbox format (- [ ] / - [x])", "README.md")

    def _check_deliverables(self, content: str) -> None:
        """Check deliverables checklist."""
        if "交付物清单" not in content:
            self._add_warning("Missing 交付物清单 section (required for new submissions)", "README.md")
            return

        required_deliverables = ["PRD", "DESIGN", "代码", "测试", "数据", "洞察", "场景"]
        missing = []
        for d in required_deliverables:
            if d not in content:
                missing.append(d)

        if missing:
            self._add_warning(f"Missing deliverable checkboxes: {', '.join(missing)}", "README.md")

    def _check_submission_checklist(self, content: str) -> None:
        """Check submission checklist."""
        if "提交前检查" not in content:
            self._add_warning("Missing 提交前检查 section", "README.md")

        required_checks = ["标题格式", "Label", "必填章节", "效率数据", "关键洞察", "代码/文档链接"]
        missing = []
        for c in required_checks:
            if c not in content:
                missing.append(c)

        if missing:
            self._add_warning(f"Submission checklist incomplete: {', '.join(missing)}", "README.md")

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
                target_path = Path.cwd() / target
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


def print_results(results: list[ValidationResult], case_name: str = "") -> None:
    """Pretty print validation results."""
    if case_name:
        print(f"\n{'=' * 60}")
        print(f"  📋 Validation: {case_name}")
        print(f"{'=' * 60}")

    errors = [r for r in results if r.severity == Severity.ERROR]
    warnings = [r for r in results if r.severity == Severity.WARNING]

    if not errors and not warnings:
        print("  ✅ All checks passed!")
        return

    if errors:
        print(f"\n  ❌ {len(errors)} Error(s):")
        for e in errors:
            loc = f" ({e.file}:{e.line})" if e.file else ""
            print(f"  {loc}  {e.message}")

    if warnings:
        print(f"\n  ⚠️  {len(warnings)} Warning(s):")
        for w in warnings:
            loc = f" ({w.file}:{w.line})" if w.file else ""
            print(f"  {loc}  {w.message}")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate case study submissions")
    parser.add_argument("--path", type=str, help="Path to single case study directory")
    parser.add_argument("--all", action="store_true", help="Validate all cases in case-studies/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    base = Path("case-studies")

    if args.all:
        case_items = sorted(
            [d for d in base.iterdir() if not d.name.startswith(".") and (d.is_dir() or d.suffix == ".md")]
        )
        if not case_items:
            print("No case studies found in case-studies/")
            return 1

        all_passed = True
        for case_item in case_items:
            validator = CaseStudyValidator(strict=args.strict)
            results = validator.validate(case_item)
            print_results(results, case_item.name)

            if any(r.severity == Severity.ERROR for r in results):
                all_passed = False

        return 0 if all_passed else 1

    elif args.path:
        case_path = Path(args.path)
        if not case_path.exists():
            print(f"Error: Path not found: {case_path}")
            return 1

        validator = CaseStudyValidator(strict=args.strict)
        results = validator.validate(case_path)
        print_results(results, case_path.name)

        if args.json:
            print(
                json.dumps(
                    [
                        {"severity": r.severity.value, "message": r.message, "file": r.file, "line": r.line}
                        for r in results
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )

        return 0 if not any(r.severity == Severity.ERROR for r in results) else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
