from pathlib import Path

from _case_study_validator_base import CaseStudyValidatorTestBase

from tools.scripts.validate_case_study import CaseStudyValidator, Severity


class TestCaseStudyValidatorLinks(CaseStudyValidatorTestBase):
    def test_trailing_whitespace_warning(self):
        """Test trailing whitespace detection."""
        content = (
            "# Test Case\n"
            "\n"
            "## 背景与挑战\n"
            "Background with trailing spaces.  \n"  # noqa: W291 - intentional
            "\n"
            "## AI 协作过程\n"
            "Phase 1: 需求\n"
            "Phase 2: 设计\n"
            "Phase 3: 实现\n"
            "Phase 4: 优化\n"
            "人 AI collaboration.\n"
            "\n"
            "## 效率对比数据\n"
            "| 阶段 | 传统方式 | AI 协作 | 提升 |\n"
            "|------|----------|---------|------|\n"
            "| 总计 | 10 小时 | 5 小时 | 2x |\n"
            "\n"
            "## 关键洞察\n"
            "### 洞察 1: Test\n"
            "Specific pattern.\n"
            "\n"
            "## 适用场景\n"
            "- [x] Web 开发\n"
        )
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("Trailing whitespace" in w.message for w in warnings))

    def test_wikilink_check(self):
        """Test wikilink validation."""
        content = """# Test Case

## 背景与挑战
Background.

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI collaboration.

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
### 洞察 1: Test
Specific pattern.

## 适用场景
- [x] Web 开发

See [[docs/nonexistent.md|Link]] for reference.
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("Broken wikilink" in w.message for w in warnings))

    def test_valid_wikilink(self):
        """Test valid wikilink passes."""
        # Create a valid docs file
        docs_dir = Path(self.test_dir) / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "api.md").write_text("# API", encoding="utf-8")

        content = """# Test Case

## 背景与挑战
Background.

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI collaboration.

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
### 洞察 1: Test
Specific pattern.

## 适用场景
- [x] Web 开发

See [[docs/api|API Reference]] for reference.
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertFalse(any("Broken wikilink" in w.message for w in warnings))
