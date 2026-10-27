from _case_study_validator_base import CaseStudyValidatorTestBase

from tools.scripts.validate_case_study import CaseStudyValidator, Severity


class TestCaseStudyValidatorStructure(CaseStudyValidatorTestBase):
    def test_vague_insights_warning(self):
        """Test vague insights trigger warning."""
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
### 洞察 1: AI 很快
AI 让开发很快很高效。

### 洞察 2: 很大提升
效果很大。

### 洞察 3: 很强大
功能很强大。

## 适用场景
- [x] Web 开发
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("vague" in w.message.lower() for w in warnings))

    def test_applicability_checkboxes(self):
        """Test applicability checkbox format validation."""
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
Web 开发
API 设计
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("checkbox format" in w.message for w in warnings))

    def test_deliverables_checklist(self):
        """Test deliverables checklist validation."""
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

## 交付物清单
- [x] PRD
- [x] 代码
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("Missing deliverable checkboxes" in w.message for w in warnings))

    def test_submission_checklist(self):
        """Test submission checklist validation."""
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

## 交付物清单
- [x] PRD
- [x] DESIGN
- [x] 代码
- [x] 测试
- [x] 数据
- [x] 洞察
- [x] 场景

## 提交前检查
- [x] 标题格式
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("Submission checklist incomplete" in w.message for w in warnings))
