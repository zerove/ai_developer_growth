import unittest

from _case_study_validator_base import CaseStudyValidatorTestBase

from tools.scripts.validate_case_study import CaseStudyValidator, Severity


class TestCaseStudyValidator(CaseStudyValidatorTestBase):
    def test_valid_new_format_case(self):
        """Test a valid new format case study passes validation."""
        content = """# Test Case Study

## 基本信息表
| 项目类型 | 规模 | 耗时 | AI 工具栈 | 效率提升 |
|----------|------|------|-----------|----------|
| Web App  | 5k LOC | 2周 | Claude, Copilot | 3.5x |

## 背景与挑战
Test background and challenges.

## AI 协作过程
### 阶段 1: 需求阶段
人: 编写 PRD
AI: 生成用户故事

### 阶段 2: 设计阶段
人: 审查架构
AI: 生成设计文档

### 阶段 3: 实现阶段
人: 代码审查
AI: 编写代码

### 阶段 4: 优化阶段
人: 性能测试
AI: 优化建议

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 需求 | 2 小时 | 30 分钟 | 4x |
| 设计 | 4 小时 | 1 小时 | 4x |
| 实现 | 20 小时 | 5 小时 | 4x |
| 优化 | 4 小时 | 1 小时 | 4x |
| 总计 | 30 小时 | 7.5 小时 | 4x |

## 关键洞察
1. **洞察 1**: 结构化 Prompt 关键
具体的结构化输入让 AI 输出更可控。

2. **洞察 2**: 人工审查不可省略
AI 生成的代码必须人工验证。

3. **洞察 3**: 迭代循环提升质量
写-审-改循环显著提升代码质量。

## 适用场景
- [x] Web 应用开发
- [x] API 设计
- [ ] 移动端开发

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

        errors = [r for r in results if r.severity == Severity.ERROR]
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")

    def test_missing_required_sections(self):
        """Test missing required sections are detected."""
        content = """# Incomplete Case Study

## Some Random Section
Only a random section.

## 关键洞察
Some insights.
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        errors = [r for r in results if r.severity == Severity.ERROR]
        self.assertGreater(len(errors), 0)
        # Should detect missing AI 协作过程, 效率对比数据, 适用场景
        error_messages = [e.message for e in errors]
        self.assertTrue(any("AI 协作过程" in msg for msg in error_messages))

    def test_legacy_format_warning(self):
        """Test legacy format triggers warning in non-strict mode."""
        content = """# Legacy Case Study

## 项目背景
Old format background.

## 1. 需求阶段
Phase 1 content.

## 关键洞察
Some insights.
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("legacy section format" in w.message for w in warnings))

    def test_strict_mode_legacy_as_error(self):
        """Test legacy format is error in strict mode."""
        content = """# Legacy Case Study

## 1. 需求阶段
Phase 1 content.

## 2. 设计阶段
Phase 2 content.
"""
        self._write_case(content)
        validator = CaseStudyValidator(strict=True)
        results = validator.validate(self.case_dir)

        errors = [r for r in results if r.severity == Severity.ERROR]
        self.assertTrue(any("legacy section format" in e.message for e in errors))

    def test_missing_efficiency_table(self):
        """Test missing efficiency table triggers warning."""
        content = """# Test Case

## 背景与挑战
Background.

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI collaboration.

## 关键洞察
### 洞察 1: Test insight
Specific numbers and patterns.

## 适用场景
- [x] Web 开发
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("效率对比数据" in w.message for w in warnings))

    def test_efficiency_table_boost_validation(self):
        """Test efficiency table boost calculation validation."""
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
| 需求 | 2 小时 | 30 分钟 | 4x |
| 总计 | 10 小时 | 5 小时 | 3x |

## 关键洞察
### 洞察 1: Test insight
Specific numbers and patterns.

## 适用场景
- [x] Web 开发
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)

        warnings = [r for r in results if r.severity == Severity.WARNING]
        # 10 hours = 600 min, 5 hours = 300 min, ratio = 2x, but claimed 3x -> should warn
        self.assertTrue(any("Boost calculation may be off" in w.message for w in warnings))


if __name__ == "__main__":
    unittest.main()
