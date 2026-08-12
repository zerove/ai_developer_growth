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
        "适用场景": ["## 适用场景", "## 适用场景与建议", "## 🎯 适用场景", "## 适用场景"],
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

        # Check for AI/Person role separation - more flexible
        role_indicators = ["人", "AI", "Human", "human", "人工", "人类", "协作", "角色", "Role", "role"]
        has_role_separation = any(indicator in content for indicator in role_indicators)

        if not has_role_separation:
            self._add_warning(
                "No clear role separation in collaboration process. Consider documenting what human did vs what AI did.",
                "README.md",
            )

    def _check_efficiency_table(self, content: str) -> None:
        """Validate efficiency comparison table."""
        if not self._has_efficiency_table(content):
            self._add_warning(
                "Missing efficiency comparison table with required columns (required for new submissions)", "README.md"
            )
            return

        data_rows = self._extract_table_rows(content)
        if not data_rows:
            self._add_error("Efficiency table found but no data rows")
            return

        self._validate_table_rows(data_rows)

    def _has_efficiency_table(self, content: str) -> bool:
        """Check if content has an efficiency table."""
        table_patterns = [
            r"\|.*阶段.*\|.*传统.*\|.*AI.*\|.*提升.*\|",
            r"\|.*指标.*\|.*优化前.*\|.*优化后.*\|.*提升.*\|",
            r"\|.*指标.*\|.*使用 AI 前.*\|.*使用 AI 后.*\|.*提升.*\|",
            r"\|.*Metric.*\|.*Before.*\|.*After.*\|.*Boost.*\|",
            r"\|.*阶段.*\|.*传统.*\|.*AI.*\|",
            r"\|.*指标.*\|.*优化前.*\|.*优化后.*\|",
            r"\|.*Metric.*\|.*Before.*\|.*After.*\|",
        ]
        return any(re.search(pattern, content) for pattern in table_patterns)

    def _extract_table_rows(self, content: str) -> list[str]:
        """Extract table data rows from content."""
        lines = content.split("\n")
        in_table = False
        data_rows = []

        for line in lines:
            if "|" in line and ("阶段" in line or "总计" in line or "指标" in line or "Metric" in line):
                in_table = True
            if in_table and line.strip().startswith("|"):
                data_rows.append(line)
            elif in_table and not line.strip().startswith("|"):
                break

        return data_rows

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
            self._add_warning(f"Could not parse efficiency values: {traditional} / {ai} → {boost}", "README.md")

    def _parse_efficiency_values(self, traditional: str, ai: str, boost: str) -> tuple[float, float, float] | None:
        """Parse efficiency values from table cells."""
        t_match = re.search(r"([\d.]+)\s*小时", traditional)
        a_match_hours = re.search(r"([\d.]+)\s*小时", ai)
        a_match_minutes = re.search(r"([\d.]+)\s*分钟", ai)
        b_match = re.search(r"([\d.]+)x", boost)

        if not (t_match and b_match and (a_match_hours or a_match_minutes)):
            return None

        t_hours = float(t_match.group(1))
        if a_match_hours:
            a_hours = float(a_match_hours.group(1))
        else:
            assert a_match_minutes is not None
            a_hours = float(a_match_minutes.group(1)) / 60
        boost_val = float(b_match.group(1))

        return (t_hours, a_hours, boost_val)

    def _check_boost_accuracy(
        self, traditional: str, ai: str, t_hours: float, a_hours: float, boost_val: float
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
            self._add_warning("Missing insights section (required for new submissions)", "README.md")
            return

        numbered = self._extract_numbered_insights(insights_text)
        if len(numbered) < 3:
            self._add_warning(f"Only {len(numbered)} numbered insights found. Recommend 3-5.", "README.md")

        self._check_insights_specificity(insights_text)

    def _extract_insights_section(self, content: str) -> str:
        """Extract insights section from content."""
        insight_headers = [
            "## 关键洞察",
            "## 💡 关键洞察",
            "## 洞察",
            "## 关键技术决策",
            "## 关键洞察与反思",
            "## 关键洞察与总结",
        ]

        for header in insight_headers:
            parts = content.split(header)
            if len(parts) >= 2:
                return parts[1]
        return ""

    def _extract_numbered_insights(self, insights_text: str) -> list[str]:
        """Extract numbered insights from text."""
        # Format 1: "1. **洞察 1** : ..."
        numbered = re.findall(r"^\d+\.\s+\*\*(洞察\s*\d+)?\*?\*\s*:?\s*(.+)$", insights_text, re.MULTILINE)
        if not numbered:
            # Format 2: "1. ..."
            numbered = re.findall(r"^\d+\.\s+(.+)$", insights_text, re.MULTILINE)
        if not numbered:
            # Format 3: bullet points
            numbered = re.findall(r"^[-*]\s+(.+)$", insights_text, re.MULTILINE)
        if not numbered:
            # Format 4: sub-headers
            numbered = re.findall(r"^###\s+\d+\.\s+(.+)$", insights_text, re.MULTILINE)
        return numbered

    def _check_insights_specificity(self, insights_text: str) -> None:
        """Check insights for specificity."""
        vague_terms = ["很快", "很高", "很大", "很多", "很强", "很方便", "很高效"]
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


def _discover_case_studies(base: Path) -> list[Path]:
    """Discover case study items in the base directory."""
    return sorted([d for d in base.iterdir() if not d.name.startswith(".") and (d.is_dir() or d.suffix == ".md")])


def _validate_all_cases(case_items: list[Path], strict: bool) -> bool:
    """Validate all case studies. Returns True if all passed."""
    all_passed = True
    for case_item in case_items:
        validator = CaseStudyValidator(strict=strict)
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
                [{"severity": r.severity.value, "message": r.message, "file": r.file, "line": r.line} for r in results],
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
                ["adg", "check", tmp, "--severity", "error", "--json"], capture_output=True, text=True, timeout=15
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
        content = open(filepath).read()
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
    parser.add_argument("--all", action="store_true", help="Validate all cases in case-studies/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--adg-scan", type=str, help="Scan code snippets in changed files")
    parser.add_argument("--auth-check", type=str, help="Check authenticity markers in changed files")
    args = parser.parse_args()

    base = Path("case-studies")

    if args.adg_scan:
        return _adg_scan(args.adg_scan)
    elif args.auth_check:
        return _auth_check(args.auth_check)
    elif args.all:
        case_items = _discover_case_studies(base)
        if not case_items:
            print("No case studies found in case-studies/")
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
