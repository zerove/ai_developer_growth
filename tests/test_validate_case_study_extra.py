"""Tests for validate_case_study.py main/print_results and edge cases."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.scripts.validate_case_study import (
    CaseStudyValidator,
    Severity,
    ValidationResult,
    main,
    print_results,
)


class TestPrintResults(unittest.TestCase):
    """Test the print_results helper."""

    def test_no_results(self) -> None:
        """No results prints success message."""
        with patch("builtins.print") as mock_print:
            print_results([], "test")
            calls = [str(c) for c in mock_print.call_args_list]
            self.assertTrue(any("All checks passed" in c for c in calls))

    def test_with_errors(self) -> None:
        """Errors are printed."""
        results = [ValidationResult(Severity.ERROR, "bad thing")]
        with patch("builtins.print") as mock_print:
            print_results(results)
            calls = [str(c) for c in mock_print.call_args_list]
            self.assertTrue(any("1 Error" in c for c in calls))

    def test_with_warnings(self) -> None:
        """Warnings are printed."""
        results = [ValidationResult(Severity.WARNING, "minor issue")]
        with patch("builtins.print") as mock_print:
            print_results(results)
            calls = [str(c) for c in mock_print.call_args_list]
            self.assertTrue(any("1 Warning" in c for c in calls))

    def test_with_file_location(self) -> None:
        """Results with file/line info show location."""
        results = [ValidationResult(Severity.ERROR, "msg", "README.md", 10)]
        with patch("builtins.print") as mock_print:
            print_results(results)
            calls = [str(c) for c in mock_print.call_args_list]
            self.assertTrue(any("README.md" in c for c in calls))


class TestCaseStudyValidatorEdgeCases(unittest.TestCase):
    """Edge case tests for CaseStudyValidator."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.case_dir = Path(self.test_dir) / "test-case"
        self.case_dir.mkdir(exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_case(self, content: str) -> None:
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")

    def test_missing_file(self) -> None:
        """Validate non-existent file returns error."""
        validator = CaseStudyValidator()
        results = validator.validate(Path(self.test_dir) / "nonexistent")
        errors = [r for r in results if r.severity == Severity.ERROR]
        self.assertTrue(any("Missing" in e.message for e in errors))

    def test_flat_md_file(self) -> None:
        """Validate a flat .md file (not directory)."""
        flat_file = Path(self.test_dir) / "flat.md"
        flat_file.write_text(
            "# Test\n"
            "## 背景与挑战\nFoo\n"
            "## AI 协作过程\nBar\n"
            "## 效率对比数据\nBaz\n"
            "## 关键洞察\n1. Insight one\n2. Insight two\n3. Insight three\n"
            "## 适用场景\n- [x] Web\n"
            "## 交付物清单\nPRD DESIGN 代码 测试 数据 洞察 场景\n"
            "## 提交前 Label 必填章节 效率数据 关键洞察 代码/文档链接\n",
            encoding="utf-8",
        )
        validator = CaseStudyValidator()
        results = validator.validate(flat_file)
        # Should not crash, should parse
        self.assertIsInstance(results, list)

    def test_efficiency_table_no_data_rows(self) -> None:
        """Efficiency table header present but no data rows."""
        content = """
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        # Should not crash; table found but no data rows may produce error
        self.assertIsInstance(results, list)

    def test_boost_calculation_minutes(self) -> None:
        """Boost with AI time in minutes (not hours)."""
        content = """# Test
与挑战
Bg

## AI 协作过程
Phase 1:
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 60 分钟 | 10x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        # 10h / 1h = 10x which matches, so no warning on boost
        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertFalse(any("Boost calculation" in w.message for w in warnings))

    def test_unparseable_efficiency_values(self) -> None:
        """Unparseable efficiency values should produce warning."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | .1.2.3 小时 | 5x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("Could not parse" in w.message for w in warnings))

    def test_no_insights_section(self) -> None:
        """No insights section at all."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        # Should not crash
        self.assertIsInstance(results, list)

    def test_no_applicability_section(self) -> None:
        """No 适用场景 section."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("适用场景" in w.message for w in warnings))

    def test_no_deliverables_section(self) -> None:
        """No 交付物清单 section."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("交付物清单" in w.message for w in warnings))

    def test_no_submission_checklist(self) -> None:
        """No 提交前检查 section."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("提交前检查" in w.message for w in warnings))

    def test_table_separator_misaligned(self) -> None:
        """Table separator row misaligned."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|:-bad---x---separator-:|:-:|:-:|:-:|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        self._write_case(content)
        validator = CaseStudyValidator()
        results = validator.validate(self.case_dir)
        warnings = [r for r in results if r.severity == Severity.WARNING]
        self.assertTrue(any("misaligned" in w.message for w in warnings))


class TestCaseStudyMain(unittest.TestCase):
    """Test the main() function."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.case_dir = Path(self.test_dir) / "test-case"
        self.case_dir.mkdir(exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_main_no_args(self) -> None:
        """main() with no args prints help and returns 1."""
        with patch("sys.argv", ["validate_case_study.py"]):
            result = main()
            self.assertEqual(result, 1)

    def test_main_path_not_found(self) -> None:
        """main() with nonexistent path returns 1."""
        with patch("sys.argv", ["validate_case_study.py", "--path", "/nonexistent"]):
            result = main()
            self.assertEqual(result, 1)

    def test_main_path_valid(self) -> None:
        """main() with valid path and valid case returns 0."""
        content = """# Test

## 背景与挑战
Bg

## AI 协作过程
Phase 1: 需求
Phase 2: 设计
Phase 3: 实现
Phase 4: 优化
人 AI

## 效率对比数据
| 阶段 | 传统方式 | AI 协作 | 提升 |
|------|----------|---------|------|
| 总计 | 10 小时 | 5 小时 | 2x |

## 关键洞察
1. **洞察 1**: Foo bar baz
2. **洞察 2**: Qux quux corge
3. **洞察 3**: Grault garply

## 适用场景
- [x] Web

## 交付物清单
PRD DESIGN 代码 测试 数据 洞察 场景

## 提交前检查
标题格式 Label 必填章节 效率数据 关键洞察 代码/文档链接
"""
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")
        with patch("sys.argv", ["validate_case_study.py", "--path", str(self.case_dir)]):
            result = main()
            self.assertEqual(result, 0)

    def test_main_path_json_output(self) -> None:
        """main() with --json outputs JSON."""
        content = "# Test\n"
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")
        with patch(
            "sys.argv",
            ["validate_case_study.py", "--path", str(self.case_dir), "--json"],
        ):
            result = main()
            # Just verify it doesn't crash
            self.assertIn(result, [0, 1])

    def test_main_path_strict(self) -> None:
        """main() with --strict mode."""
        content = """# Test

## 1. 需求阶段
Old format.
"""
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")
        with patch(
            "sys.argv",
            ["validate_case_study.py", "--path", str(self.case_dir), "--strict"],
        ):
            result = main()
            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
