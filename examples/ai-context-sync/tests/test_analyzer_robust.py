import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzer import GitAnalyzer

class TestGitAnalyzerRobust(unittest.TestCase):
    def setUp(self):
        # 初始化带忽略模式的分析器
        self.analyzer = GitAnalyzer(ignore_patterns=["package-lock.json"])

    def test_filter_diff_with_unidiff_parsing(self):
        # 这是一个使用 unidiff 可以正确解析的典型 git diff 格式
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "index 83db489..7b8e5c1 100644\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-print('hi')\n"
            "+print('hello')\n"
        )
        # 暂时断言它不抛出异常，并返回非空
        result = self.analyzer.filter_diff(diff)
        self.assertIn("src/main.py", result)
        self.assertIn("+print('hello')", result)

    def test_filter_diff_removes_ignored_file(self):
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n+++ b/src/main.py\n"
            "@@ -1,1 +1,1 @@\n-old\n+new\n"
            "diff --git a/package-lock.json b/package-lock.json\n"
            "--- a/package-lock.json\n+++ b/package-lock.json\n"
            "@@ -1,1 +1,1 @@\n-lock\n+lock\n"
        )
        result = self.analyzer.filter_diff(diff)
        self.assertIn("src/main.py", result)
        self.assertNotIn("package-lock.json", result)

    def test_filter_diff_with_corrupted_diff_fallback(self):
        # 损坏的 diff，没有有效的 git header，这将强制触发异常并进入 _basic_filter
        corrupted_diff = "not a valid diff file content"
        
        # 即使损坏，也应该返回一些内容或者不崩溃（基于 basic_filter 的逻辑）
        result = self.analyzer.filter_diff(corrupted_diff)
        # 基础过滤在没有找到 diff --git 时返回空或者原内容。此处应该返回空或原内容
        # 关键是不会抛出异常
        self.assertIsNotNone(result)

if __name__ == "__main__":
    unittest.main()
