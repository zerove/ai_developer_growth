"""Tests for src/tester.py - TestRunner and TestResult"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tester import TestResult, TestRunner


class TestTestResult:
    def test_named_tuple(self):
        result = TestResult(success=True, output="ok", exit_code=0)
        assert result.success is True
        assert result.output == "ok"
        assert result.exit_code == 0

    def test_fields(self):
        result = TestResult(success=False, output="fail", exit_code=1)
        assert result[0] is False
        assert result[1] == "fail"
        assert result[2] == 1


class TestTestRunner:
    def test_init_default_timeout(self):
        runner = TestRunner()
        assert runner.timeout == 30

    def test_init_custom_timeout(self):
        runner = TestRunner(timeout=60)
        assert runner.timeout == 60

    def test_run_test_passing(self):
        runner = TestRunner(timeout=10)
        test_code = "def test_pass(): assert True"
        result = runner.run_test(test_code, [])
        assert isinstance(result, TestResult)
        assert result.exit_code == 0

    def test_run_test_failing(self):
        runner = TestRunner(timeout=10)
        test_code = "def test_fail(): assert False, 'intentional failure'"
        result = runner.run_test(test_code, [])
        assert result.success is False
        assert result.exit_code != 0

    def test_run_test_timeout(self):
        runner = TestRunner(timeout=1)
        test_code = "import time; def test_timeout(): time.sleep(5)"
        result = runner.run_test(test_code, [])
        # Should timeout - either exit_code 124 or error
        assert result.success is False

    def test_run_test_with_target_file(self):
        runner = TestRunner(timeout=10)
        # Create a temp file in a subdirectory to avoid SameFileError
        tmpdir = tempfile.mkdtemp()
        target_dir = os.path.join(tmpdir, "pkg")
        os.makedirs(target_dir)
        target_file = os.path.join(target_dir, "target_module.py")
        with open(target_file, "w") as f:
            f.write("VALUE = 42\n")
        try:
            test_code = "from pkg.target_module import VALUE; def test_val(): assert VALUE == 42"
            rel_target = os.path.relpath(target_file, tmpdir)
            result = runner.run_test(test_code, [rel_target])
            assert isinstance(result, TestResult)
        finally:
            shutil.rmtree(tmpdir)

    def test_run_test_invalid_code(self):
        runner = TestRunner(timeout=10)
        test_code = "this is not valid python code {{{"
        result = runner.run_test(test_code, [])
        assert result.success is False
