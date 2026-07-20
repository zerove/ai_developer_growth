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
        "背景与挑战": ["## 背景与挑战", "## 项目背景", "## 项目背景与挑战"],
        "AI 协作过程": ["## AI 协作过程", "## 1. 需求阶段", "## 需求阶段", "## 1. 需求阶段"],
        "效率对比数据": ["## 效率对比数据", "## 效率提升分析", "## 效率对比"],
        "关键洞察": ["## 关键洞察", "## 关键洞察与反思"],
        "适用场景": ["## 适用场景", "## 适用场景与建议"],
        "交付物清单": ["## 交付物清单", "## 交付物"],
        "提交前检查": ["## 提交前检查", "## 提交清单"],
    }

    REQUIRED_TABLES = [
        "效率对比数据",
        "交付物清单",
    ]

    PHASE_KEYWORDS = [
        "阶段 1", "阶段 2", "阶段 3", "阶段 4",
        "需求", "架构", "编码", "优化"
    ]

    def __init__(self, strict: bool = False):
        self.strict = strict
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
        lines = content.split('\n')

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

    def _check_sections(self, content: str):
        """Verify all required sections exist (supports alt headers)."""
        for section_name, alt_headers in self.REQUIRED_SECTIONS_ALT.items():
            found = False
            for alt in alt_headers:
                if alt in content:
                    found = True
                    break
            if not found:
                self._add_error(f"Missing required section: {section_name} (tried: {', '.join(alt_headers)})")

    def _check_tables(self, content: str):
        """Verify required tables exist."""
        for table in self.REQUIRED_TABLES:
            if table not in content:
                self._add_error(f"Missing required table: {table}")

    def _check_phases(self, content: str):
        """Verify AI collaboration phases are documented."""
        found_phases = 0
        for kw in self.PHASE_KEYWORDS:
            if kw in content:
                found_phases += 1

        if found_phases < 3:
            self._add_warning(
                f"Only {found_phases}/8 phase keywords found. "
                "Consider documenting all 4 phases explicitly.",
                "README.md"
            )

        # Check for AI/Person role separation
        if "人" not in content or "AI" not in content:
            self._add_warning(
                "No clear 人/AI role separation in collaboration process. "
                "Record what human did vs what AI did.",
                "README.md"
            )

    def _check_efficiency_table(self, content: str):
        """Validate efficiency comparison table."""
        # Find the efficiency table
        table_pattern = r'\|.*阶段.*\|.*传统.*\|.*AI.*\|.*提升.*\|'
        if not re.search(table_pattern, content):
            self._add_error("Missing efficiency comparison table with required columns")
            return

        # Extract table rows
        lines = content.split('\n')
        in_table = False
        data_rows = []

        for line in lines:
            if '|' in line and ('阶段' in line or '总计' in line):
                in_table = True
            if in_table and line.strip().startswith('|'):
                data_rows.append(line)
            elif in_table and not line.strip().startswith('|'):
                break

        if not data_rows:
            self._add_error("Efficiency table found but no data rows")
            return

        # Parse and validate
        for row in data_rows:
            if row.strip() in ['|---|', '| --- |', '|:---|']:
                continue
            cols = [c.strip() for c in row.split('|')[1:-1]]
            if len(cols) >= 4:
                stage, traditional, ai, boost = cols[:4]
                if stage in ['总计', '总计 '] or '总计' in stage:
                    self._validate_boost_calculation(traditional, ai, boost)

    def _validate_boost_calculation(self, traditional: str, ai: str, boost: str):
        """Validate that boost = traditional / ai (in hours)."""
        try:
            # Extract numbers
            t_match = re.search(r'([\d.]+)\s*小时', traditional)
            a_match = re.search(r'([\d.]+)\s*分钟', ai)
            b_match = re.search(r'([\d.]+)x', boost)

            if t_match and a_match and b_match:
                t_hours = float(t_match.group(1))
                a_minutes = float(a_match.group(1))
                boost_val = float(b_match.group(1))

                expected = t_hours / (a_minutes / 60)
                if abs(expected - boost_val) > 0.5:  # Allow 0.5x tolerance
                    self._add_warning(
                        f"Boost calculation may be off: {traditional} / ({ai} min) = {expected:.1f}x, claimed {boost_val}x",
                        "README.md"
                    )
        except (ValueError, AttributeError):
            self._add_warning(f"Could not parse efficiency values: {traditional} / {ai} → {boost}", "README.md")

    def _check_insights(self, content: str):
        """Validate key insights quality."""
        insight_section = content.split("## 关键洞察")
        if len(insight_section) < 2:
            return

        insights_text = insight_section[1]
        # Count numbered insights
        numbered = re.findall(r'^\d+\.\s+\*\*(洞察\s*\d+)?\*?\*\s*:?\s*(.+)$', insights_text, re.MULTILINE)
        if len(numbered) < 3:
            self._add_warning(f"Only {len(numbered)} numbered insights found. Recommend 3-5.", "README.md")

        # Check for specificity
        vague_terms = ["很快", "很高", "很大", "很多", "很强", "很方便", "很高效", "提升"]
        for term in vague_terms:
            if term in insights_text.lower() and "具体" not in insights_text.lower():
                self._add_warning(f"Insights may be vague (contains '{term}'). Use specific numbers/patterns.", "README.md")
                break

    def _check_applicability(self, content: str):
        """Check applicability scenarios are marked."""
        if "适用场景" not in content:
            self._add_error("Missing 适用场景 section")
            return

        # Check for checkboxes
        if '- [ ]' not in content and '- [x]' not in content:
            self._add_warning("Applicability scenarios should use checkbox format (- [ ] / - [x])", "README.md")

    def _check_deliverables(self, content: str):
        """Check deliverables checklist."""
        if "交付物清单" not in content:
            self._add_error("Missing 交付物清单 section")
            return

        required_deliverables = ["PRD", "DESIGN", "代码", "测试", "数据", "洞察", "场景"]
        missing = []
        for d in required_deliverables:
            if d not in content:
                missing.append(d)

        if missing:
            self._add_warning(f"Missing deliverable checkboxes: {', '.join(missing)}", "README.md")

    def _check_submission_checklist(self, content: str):
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

    def _check_format(self, lines: list[str]):
        """Check markdown formatting."""
        for i, line in enumerate(lines, 1):
            # Check for table alignment
            if '|' in line and '---' in line:
                # Header separator row
                if not re.match(r'^\|[\s\-\:|]+\|$', line):
                    self._add_warning(f"Table separator misaligned at line {i}", "README.md", i)

            # Check for unescaped pipes in code blocks
            if '```' in line:
                pass  # Skip inside code blocks

            # Check for trailing whitespace
            if line.endswith('  ') or line.endswith('\t'):
                self._add_warning(f"Trailing whitespace at line {i}", "README.md", i)

    def _check_links(self, case_path: Path, content: str):
        """Check wikilinks and external links."""
        # Check wikilinks
        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        for link in wikilinks:
            # Check if target exists
            if '|' in link:
                target = link.split('|')[0].strip()
            else:
                target = link.strip()

            if target.startswith('docs/') or target.startswith('case-studies/') or target.startswith('examples/'):
                target_path = Path.cwd() / target
                if not target_path.exists():
                    # Try with .md extension
                    if not (target_path.with_suffix('.md')).exists():
                        self._add_warning(f"Broken wikilink: [[{link}]] -> {target_path}", "README.md")

    def _add_error(self, msg: str, file: str = "", line: int = 0):
        self.results.append(ValidationResult(Severity.ERROR, msg, file, line))

    def _add_warning(self, msg: str, file: str = "", line: int = 0):
        if self.strict:
            self._add_error(msg, file, line)
        else:
            self.results.append(ValidationResult(Severity.WARNING, msg, file, line))


def print_results(results: list[ValidationResult], case_name: str = ""):
    """Pretty print validation results."""
    if case_name:
        print(f"\n{'='*60}")
        print(f"  📋 Validation: {case_name}")
        print(f"{'='*60}")

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


def main():
    parser = argparse.ArgumentParser(description="Validate case study submissions")
    parser.add_argument("--path", type=str, help="Path to single case study directory")
    parser.add_argument("--all", action="store_true", help="Validate all cases in case-studies/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    base = Path("case-studies")

    if args.all:
        case_items = sorted([
            d for d in base.iterdir()
            if not d.name.startswith('.') and (d.is_dir() or d.suffix == '.md')
        ])
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
            print(json.dumps([{
                "severity": r.severity.value,
                "message": r.message,
                "file": r.file,
                "line": r.line
            } for r in results], ensure_ascii=False, indent=2))

        return 0 if not any(r.severity == Severity.ERROR for r in results) else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
