import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.scripts.validate_case_study import CaseStudyValidator, Severity


class TestCaseStudyValidator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.case_dir = Path(self.test_dir) / "test-case"
        self.case_dir.mkdir(exist_ok=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_case(self, content: str):
        """Write case study content to README.md"""
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")

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


class TestValidateCaseStudyMain(unittest.TestCase):
    """Test CLI main function via subprocess."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.case_dir = Path(self.test_dir) / "test-case"
        self.case_dir.mkdir(exist_ok=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_case(self, content: str):
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")

    def _run_main(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "/home/zeron/dev/ai_developer_growth/tools/scripts/validate_case_study.py",
                *args,
            ],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )

    def test_main_no_args(self):
        """Test main shows help when no args."""
        result = self._run_main()
        self.assertEqual(result.returncode, 1)
        self.assertIn("usage", result.stdout.lower())

    def test_main_with_path(self):
        """Test main with --path to valid case."""
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
### 洞察 1: Test insight
Specific numbers and patterns.

## 适用场景
- [x] Web 开发
"""
        self._write_case(content)
        result = self._run_main("--path", str(self.case_dir))
        self.assertEqual(result.returncode, 0)

    def test_main_path_not_found(self):
        """Test main with non-existent path."""
        result = self._run_main("--path", "/nonexistent/path")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error", result.stdout)

    def test_main_with_json_output(self):
        """Test main with --json flag."""
        content = """# Test

## 背景与挑战
Background.

## AI 协作过程
人 AI collaboration.

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
### 洞察 1: Test
Specific.

## 适用场景
- [x] Web 开发
"""
        self._write_case(content)
        result = self._run_main("--path", str(self.case_dir), "--json")
        self.assertEqual(result.returncode, 0)
        # JSON should be in stdout
        self.assertIn("[", result.stdout)

    def test_main_with_all_flag_empty(self):
        """Test main with --all flag in empty directory."""
        result = self._run_main("--all")
        self.assertEqual(result.returncode, 1)
        # Output may be on stderr or stdout
        combined = result.stdout + result.stderr
        self.assertTrue("No case studies found" in combined or "error" in combined.lower() or result.returncode == 1)

    def test_main_with_strict_flag(self):
        """Test main with --strict flag."""
        content = """# Test

## 1. 需求阶段
Legacy format.
"""
        self._write_case(content)
        result = self._run_main("--path", str(self.case_dir), "--strict")
        # Strict mode should report errors for legacy format
        self.assertEqual(result.returncode, 1)

    def test_print_results_no_issues(self):
        """Test print_results with no issues."""
        from tools.scripts.validate_case_study import print_results

        results = []
        # Should print "All checks passed"
        print_results(results, "test")


if __name__ == "__main__":
    unittest.main()
