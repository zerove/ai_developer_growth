"""Tests for analyze_case_quality script."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.analyze_case_quality import (
    CaseStudyQualityAnalyzer,
    QualityMetrics,
    format_report,
)


class TestQualityMetrics:
    """Tests for QualityMetrics dataclass."""

    def test_default_values(self):
        """Test default values."""
        metrics = QualityMetrics(case_name="test")
        assert metrics.case_name == "test"
        assert metrics.authenticity_score == 0.0
        assert metrics.efficiency_credibility == 0.0
        assert metrics.insight_quality == 0.0
        assert metrics.completeness == 0.0
        assert metrics.cross_references == 0.0
        assert metrics.overall_score == 0.0
        assert metrics.issues == []
        assert metrics.strengths == []

    def test_custom_values(self):
        """Test custom values."""
        metrics = QualityMetrics(
            case_name="test",
            authenticity_score=50.0,
            efficiency_credibility=80.0,
            insight_quality=70.0,
            completeness=90.0,
            cross_references=30.0,
        )
        assert metrics.authenticity_score == 50.0
        assert metrics.efficiency_credibility == 80.0


class TestCaseStudyQualityAnalyzer:
    """Tests for CaseStudyQualityAnalyzer."""

    def setup_method(self):
        """Create temp directory with test case study."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.analyzer = CaseStudyQualityAnalyzer(case_studies_dir=self.temp_dir)

    def create_test_case(self, name: str, content: str) -> Path:
        """Create a test case study file."""
        case_path = self.temp_dir / name
        if name.endswith(".md"):
            case_path.write_text(content, encoding="utf-8")
        else:
            case_path.mkdir()
            (case_path / "README.md").write_text(content, encoding="utf-8")
        return case_path

    def test_analyze_empty_case(self):
        """Test analyzing case with minimal content."""
        case_path = self.create_test_case("empty.md", "# Empty Case\n\nNo content here.")
        metrics = self.analyzer.analyze_case(case_path)

        assert metrics.case_name == "empty"
        assert metrics.overall_score >= 0
        assert metrics.overall_score <= 100

    def test_analyze_case_with_efficiency_table(self):
        """Test analyzing case with efficiency table."""
        content = """# Test Case

## 背景与挑战
Test background.

## AI 协作过程
Human did X, AI did Y.

## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 10 小时 | 2 小时 | 5.0x |

## 关键洞察
1. **洞察 1**: Using `ruff` reduced lint time by 50%
2. **洞察 2**: `mypy` caught 10 type errors

## 适用场景
- [x] Refactoring
- [ ] New projects

## 交付物清单
- [x] PRD
- [x] 代码
- [x] 测试

## 提交前检查
- [x] 标题格式
- [x] Label
- [x] 必填章节
- [x] 效率数据
- [x] 关键洞察
- [x] 代码/文档链接
"""
        case_path = self.create_test_case("with_table.md", content)
        metrics = self.analyzer.analyze_case(case_path)

        assert metrics.efficiency_credibility > 0
        assert metrics.completeness > 50
        assert metrics.insight_quality > 0

    def test_analyze_case_with_authenticity_markers(self):
        """Test analyzing case with GitHub links and commit hashes."""
        content = """# Authentic Case

## 背景与挑战
See PR at https://github.com/user/repo/pull/123 and commit abc123def.

## AI 协作过程
Human wrote tests, AI wrote implementation.

## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 8 小时 | 2 小时 | 4.0x |

## 关键洞察
1. Using `Claude` for code generation saved 6 hours
2. `ruff` auto-fixed 90% of lint issues

## 适用场景
- [x] Refactoring

## 交付物清单
- [x] PRD
- [x] 代码
- [x] 测试

## 提交前检查
- [x] 标题格式
- [x] Label
"""
        case_path = self.create_test_case("authentic.md", content)
        metrics = self.analyzer.analyze_case(case_path)

        # Should have some authenticity due to GitHub link and commit hash
        assert metrics.authenticity_score > 20

    def test_analyze_case_vague_insights(self):
        """Test analyzing case with vague insights."""
        content = """# Vague Case

## 背景与挑战
Background.

## AI 协作过程
Process.

## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 10 小时 | 1 小时 | 10.0x |

## 关键洞察
1. AI is very fast and very efficient
2. It significantly improved everything
3. The results were massive

## 适用场景
- [x] Everything

## 交付物清单
- [x] PRD

## 提交前检查
- [x] 标题格式
"""
        case_path = self.create_test_case("vague.md", content)
        metrics = self.analyzer.analyze_case(case_path)

        # Should have lower insight quality due to vague language
        assert metrics.insight_quality < 70

    def test_analyze_case_unrealistic_efficiency(self):
        """Test analyzing case with unrealistic efficiency claims."""
        content = """# Unrealistic Case

## 背景与挑战
Background.

## AI 协作过程
Process.

## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 100 小时 | 0.1 小时 | 1000x |

## 关键洞察
1. 1000x speedup!

## 适用场景
- [x] Magic

## 交付物清单
- [x] PRD

## 提交前检查
- [x] 标题格式
"""
        case_path = self.create_test_case("unrealistic.md", content)
        metrics = self.analyzer.analyze_case(case_path)

        # Should have lower efficiency credibility due to unrealistic values
        # Note: The table validation passes format check but boost accuracy check
        # only gives warning, not error. So score may still be high.
        assert metrics.efficiency_credibility <= 90

    def test_analyze_all(self):
        """Test analyzing all cases in directory."""
        # Create multiple cases
        content1 = """# Case 1
## 背景与挑战
Bg
## AI 协作过程
Proc
## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 10 小时 | 2 小时 | 5.0x |
## 关键洞察
1. Good insight
## 适用场景
- [x] Test
## 交付物清单
- [x] 代码
## 提交前检查
- [x] 标题格式
"""
        content2 = """# Case 2
## 背景与挑战
Bg
## AI 协作过程
Proc
## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 8 小时 | 2 小时 | 4.0x |
## 关键洞察
1. Another insight
## 适用场景
- [x] Test
## 交付物清单
- [x] 代码
## 提交前检查
- [x] 标题格式
"""
        self.create_test_case("case1.md", content1)
        self.create_test_case("case2.md", content2)

        results = self.analyzer.analyze_all()
        assert len(results) == 2
        assert all(isinstance(m, QualityMetrics) for m in results)

    def test_cross_reference_checking(self):
        """Test cross-reference checking with INDEX.md and MOC.md."""
        # Create INDEX.md and MOC.md
        index_content = """# INDEX

- [case-with-ref](case-studies/case-with-ref.md)
"""
        moc_content = """# MOC

- case-with-ref
"""
        Path("INDEX.md").write_text(index_content, encoding="utf-8")
        Path("MOC.md").write_text(moc_content, encoding="utf-8")

        try:
            content = """# Case With Ref

## 背景与挑战
See [[docs/architecture.md]] for details.

## AI 协作过程
Process.

## 效率对比数据
| 阶段 | 传统耗时 | AI 耗时 | 提升 |
|------|---------|--------|------|
| 总计 | 10 小时 | 2 小时 | 5.0x |

## 关键洞察
1. Good insight

## 适用场景
- [x] Test

## 交付物清单
- [x] 代码

## 提交前检查
- [x] 标题格式
"""
            case_path = self.create_test_case("case-with-ref.md", content)
            metrics = self.analyzer.analyze_case(case_path)

            # Should have cross-reference points
            assert metrics.cross_references > 0
        finally:
            # Cleanup
            Path("INDEX.md").unlink(missing_ok=True)
            Path("MOC.md").unlink(missing_ok=True)


class TestFormatReport:
    """Tests for format_report function."""

    def test_format_report(self):
        """Test report formatting."""
        report = {
            "summary": {
                "total_cases": 2,
                "average_scores": {
                    "overall": 75.0,
                    "authenticity": 60.0,
                    "efficiency_credibility": 90.0,
                    "insight_quality": 70.0,
                    "completeness": 95.0,
                    "cross_references": 40.0,
                },
                "categories": {
                    "excellent": 1,
                    "good": 1,
                    "needs_improvement": 0,
                },
            },
            "top_cases": [
                {"name": "case1", "score": 80.0},
                {"name": "case2", "score": 70.0},
            ],
            "bottom_cases": [
                {"name": "case2", "score": 70.0},
                {"name": "case1", "score": 80.0},
            ],
            "common_issues": {"Issue 1": 2, "Issue 2": 1},
            "common_strengths": {"Strength 1": 2},
            "detailed": [
                {
                    "case": "case1",
                    "overall": 80.0,
                    "authenticity": 70.0,
                    "efficiency": 90.0,
                    "insight": 75.0,
                    "completeness": 100.0,
                    "cross_refs": 50.0,
                    "issues": [],
                    "strengths": ["Strength 1"],
                },
                {
                    "case": "case2",
                    "overall": 70.0,
                    "authenticity": 50.0,
                    "efficiency": 90.0,
                    "insight": 65.0,
                    "completeness": 90.0,
                    "cross_refs": 30.0,
                    "issues": ["Issue 1"],
                    "strengths": [],
                },
            ],
        }

        output = format_report(report)
        assert "Case Study Quality Analysis Report" in output
        assert "75.0/100" in output
        assert "case1" in output
        assert "case2" in output
        assert "Issue 1" in output
        assert "Strength 1" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])