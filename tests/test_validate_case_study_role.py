from _case_study_validator_base import CaseStudyValidatorTestBase

from tools.scripts.validate_case_study import CaseStudyValidator, Severity


class TestCaseStudyValidatorRole(CaseStudyValidatorTestBase):
    def test_phase_keywords_detection(self):
        """Test phase keyword detection."""
        content = """# Test Case

## 背景与挑战
Background.

## AI 协作过程
Just some text without phase keywords.

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
### 洞察 1: Test
Specific pattern.

## 适用场景
- [x] Web 开发
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("phase keywords found" in w.message or "phase keywords" in w.message for w in warnings))

    def test_ai_human_role_separation(self):
        """Test AI/human role separation check - proper content should pass."""
        content = """# Test Case

## 背景与挑战
Background.

## AI 协作过程
Phase 1: Requirement analysis
Phase 2: Architecture design
Phase 3: Implementation
Phase 4: Optimization
Human wrote PRD, AI generated code.

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
### 洞察 1: Test
Specific pattern.

### 洞察 2: Test2
Specific pattern.

### 洞察 3: Test3
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
- [x] Label
- [x] 必填章节
- [x] 效率数据
- [x] 关键洞察
- [x] 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        # Should have no role separation warning since "Human" and "AI" are present
        warnings = [r for r in results if r.severity == Severity.WARNING]
        role_warnings = [w for w in warnings if "role separation" in w.message]
        self.assertEqual(
            len(role_warnings),
            0,
            f"Unexpected role separation warning: {role_warnings}",
        )

    def test_ai_human_role_separation_warning(self):
        """Test that missing role separation triggers warning."""
        content = """# Test Case

## 背景与挑战
Background.

## 工作流程
Phase 1: Requirement analysis
Phase 2: Architecture design
Phase 3: Implementation
Phase 4: Optimization
Just text without any indicators.

## 效率对比数据
| 阶段 | 传统手段 | 新方法 | 提升 |
|------|----------|--------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
### 洞察 1: Test
Specific pattern.

### 洞察 2: Test2
Specific pattern.

### 洞察 3: Test3
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
- [x] Label
- [x] 必填章节
- [x] 效率数据
- [x] 关键洞察
- [x] 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        # Should have role separation warning since no "Human"/"AI"/"人" etc.
        warnings = [r for r in results if r.severity == Severity.WARNING]
        role_warnings = [w for w in warnings if "role separation" in w.message]
        self.assertEqual(len(role_warnings), 1, f"Expected role separation warning: {role_warnings}")
