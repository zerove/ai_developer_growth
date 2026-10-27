import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
        empty_dir = Path(self.test_dir) / "empty"
        empty_dir.mkdir()
        result = self._run_main("--all", "--base", str(empty_dir))
        self.assertEqual(result.returncode, 1)
        combined = result.stdout + result.stderr
        self.assertIn("No case studies", combined)

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
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_results(results, "test")
        assert "All checks passed" in buf.getvalue()
