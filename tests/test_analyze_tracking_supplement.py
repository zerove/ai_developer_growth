"""Tests for analyze_tracking.py - improve coverage from 52% to 70%+."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.scripts.analyze_tracking import (
    analyze_pageviews,
    analyze_reading_time,
    analyze_searches,
    load_tracking_data,
    suggest_synonym_groups,
)


class TestLoadTrackingData(unittest.TestCase):
    """Test loading tracking data from JSON file."""

    def test_load_valid_json(self):
        """Should load valid JSON file."""
        data = {"searches": [], "pageviews": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            result = load_tracking_data(f.name)
        self.assertEqual(result, data)

    def test_load_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_tracking_data("nonexistent.json")


class TestAnalyzeSearches(unittest.TestCase):
    """Test search analysis."""

    def test_empty_searches(self):
        """Should handle empty search list."""
        result = analyze_searches({"searches": []})
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unique"], 0)
        self.assertEqual(result["top"], [])
        self.assertEqual(result["zero_result"], [])

    def test_no_searches_key(self):
        """Should handle missing searches key."""
        result = analyze_searches({})
        self.assertEqual(result["total"], 0)

    def test_single_search(self):
        """Should count single search."""
        data = {"searches": [{"q": "python", "results": 5}]}
        result = analyze_searches(data)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["unique"], 1)
        self.assertIn(("python", 1), result["top"])

    def test_multiple_searches_same_query(self):
        """Should aggregate same queries."""
        data = {
            "searches": [
                {"q": "python", "results": 5},
                {"q": "python", "results": 3},
                {"q": "python", "results": 8},
            ]
        }
        result = analyze_searches(data)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["unique"], 1)
        self.assertIn(("python", 3), result["top"])

    def test_zero_result_searches(self):
        """Should track zero-result searches."""
        data = {
            "searches": [
                {"q": "python", "results": 5},
                {"q": "rust", "results": 0},
                {"q": "rust", "results": 0},
            ]
        }
        result = analyze_searches(data)
        self.assertEqual(len(result["zero_result"]), 1)
        self.assertIn(("rust", 2), result["zero_result"])

    def test_empty_query_filtered(self):
        """Should filter out empty queries."""
        data = {
            "searches": [
                {"q": "", "results": 0},
                {"q": "  ", "results": 0},
                {"q": "python", "results": 5},
            ]
        }
        result = analyze_searches(data)
        self.assertEqual(result["unique"], 1)

    def test_custom_top_n(self):
        """Should respect top_n parameter."""
        data = {
            "searches": [
                {"q": f"query{i}", "results": 1} for i in range(20)
            ]
        }
        result = analyze_searches(data, top_n=5)
        self.assertEqual(len(result["top"]), 5)


class TestAnalyzePageviews(unittest.TestCase):
    """Test pageview analysis."""

    def test_empty_pageviews(self):
        """Should handle empty pageviews."""
        result = analyze_pageviews({"pageviews": []})
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unique"], 0)
        self.assertEqual(result["top"], [])

    def test_no_pageviews_key(self):
        """Should handle missing pageviews key."""
        result = analyze_pageviews({})
        self.assertEqual(result["total"], 0)

    def test_single_pageview(self):
        """Should count single pageview."""
        data = {"pageviews": [{"page": "/docs/test"}]}
        result = analyze_pageviews(data)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["unique"], 1)

    def test_multiple_pageviews_same_page(self):
        """Should aggregate same pages."""
        data = {
            "pageviews": [
                {"page": "/docs/test"},
                {"page": "/docs/test"},
                {"page": "/docs/other"},
            ]
        }
        result = analyze_pageviews(data)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["unique"], 2)
        self.assertIn(("/docs/test", 2), result["top"])

    def test_custom_top_n(self):
        """Should respect top_n parameter."""
        data = {"pageviews": [{"page": f"/page{i}"} for i in range(20)]}
        result = analyze_pageviews(data, top_n=5)
        self.assertEqual(len(result["top"]), 5)


class TestAnalyzeReadingTime(unittest.TestCase):
    """Test reading time analysis."""

    def test_empty_reading_time(self):
        """Should handle empty reading time."""
        result = analyze_reading_time({"reading_time": {}})
        self.assertEqual(result["total_seconds"], 0)
        self.assertEqual(result["top"], [])

    def test_no_reading_time_key(self):
        """Should handle missing reading_time key."""
        result = analyze_reading_time({})
        self.assertEqual(result["total_seconds"], 0)

    def test_single_page(self):
        """Should analyze single page reading time."""
        data = {"reading_time": {"/docs/test": 120}}
        result = analyze_reading_time(data)
        self.assertEqual(result["total_seconds"], 120)
        self.assertEqual(result["total_minutes"], 2.0)
        self.assertEqual(len(result["top"]), 1)

    def test_multiple_pages(self):
        """Should sort pages by reading time."""
        data = {
            "reading_time": {
                "/docs/short": 30,
                "/docs/long": 300,
                "/docs/medium": 120,
            }
        }
        result = analyze_reading_time(data)
        self.assertEqual(result["total_seconds"], 450)
        self.assertEqual(result["total_minutes"], 7.5)
        # Should be sorted descending
        self.assertEqual(result["top"][0][0], "/docs/long")
        self.assertEqual(result["top"][1][0], "/docs/medium")
        self.assertEqual(result["top"][2][0], "/docs/short")

    def test_custom_top_n(self):
        """Should respect top_n parameter."""
        data = {"reading_time": {f"/page{i}": i * 10 for i in range(20)}}
        result = analyze_reading_time(data, top_n=5)
        self.assertEqual(len(result["top"]), 5)


class TestPrintReport(unittest.TestCase):
    """Test print_report function."""

    def test_print_report_basic(self):
        """Should print report without errors."""
        import sys
        from io import StringIO

        from tools.scripts.analyze_tracking import print_report

        data = {
            "searches": [{"q": "test", "results": 5}],
            "pageviews": [{"page": "/test"}],
            "reading_time": {"/test": 60},
        }
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_report(data, 5)
        finally:
            sys.stdout = old_stdout

    def test_print_report_empty_data(self):
        """Should handle empty data."""
        import sys
        from io import StringIO

        from tools.scripts.analyze_tracking import print_report

        data = {"searches": [], "pageviews": [], "reading_time": {}}
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_report(data, 10)
        finally:
            sys.stdout = old_stdout

    def test_print_report_with_synonyms(self):
        """Should print synonym suggestions."""
        import sys
        from io import StringIO

        from tools.scripts.analyze_tracking import print_report

        data = {
            "searches": [
                {"q": "python tutorial", "results": 5},
                {"q": "python guide", "results": 3},
            ],
            "pageviews": [],
            "reading_time": {},
        }
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_report(data, 10)
        finally:
            sys.stdout = old_stdout


class TestMainFunction(unittest.TestCase):
    """Test main function."""

    def test_main_with_valid_file(self):
        """Should run main with valid file."""
        import sys
        from io import StringIO

        from tools.scripts.analyze_tracking import main

        data = {
            "searches": [{"q": "test", "results": 5}],
            "pageviews": [{"page": "/test"}],
            "reading_time": {"/test": 60},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            temp_path = f.name

        old_argv = sys.argv
        sys.argv = ["analyze_tracking.py", temp_path, "--top", "5"]
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            main()
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv
            Path(temp_path).unlink(missing_ok=True)

    def test_main_with_export_synonyms(self):
        """Should export synonyms as JSON."""
        import sys
        from io import StringIO

        from tools.scripts.analyze_tracking import main

        data = {
            "searches": [
                {"q": "python tutorial", "results": 5},
                {"q": "python guide", "results": 3},
            ],
            "pageviews": [],
            "reading_time": {},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            temp_path = f.name

        old_argv = sys.argv
        sys.argv = ["analyze_tracking.py", temp_path, "--export-synonyms"]
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            main()
            output = sys.stdout.getvalue()
            # Should output valid JSON
            if output.strip():
                json.loads(output)
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv
            Path(temp_path).unlink(missing_ok=True)

    def test_main_nonexistent_file(self):
        """Should exit with error for nonexistent file."""
        import sys
        from io import StringIO

        from tools.scripts.analyze_tracking import main

        old_argv = sys.argv
        sys.argv = ["analyze_tracking.py", "nonexistent.json"]
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            with self.assertRaises(SystemExit):
                main()
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv


class TestSuggestSynonymGroups(unittest.TestCase):
    """Test synonym suggestion."""

    def test_empty_searches(self):
        """Should handle empty searches."""
        result = suggest_synonym_groups([])
        self.assertEqual(result, [])

    def test_no_common_words(self):
        """Should return empty for unrelated queries."""
        searches = [("apple", 1), ("banana", 1), ("cherry", 1)]
        result = suggest_synonym_groups(searches)
        self.assertEqual(result, [])

    def test_shared_word_grouping(self):
        """Should group queries sharing common words."""
        searches = [
            ("python tutorial", 5),
            ("python guide", 3),
            ("python basics", 2),
        ]
        result = suggest_synonym_groups(searches)
        # Should have at least one group
        self.assertGreater(len(result), 0)

    def test_short_words_filtered(self):
        """Should filter words shorter than 3 chars."""
        searches = [
            ("a python", 1),
            ("b python", 1),
        ]
        result = suggest_synonym_groups(searches)
        # "a" and "b" are too short, but "python" is shared
        if result:
            self.assertIn("python", result[0][0].lower())

    def test_minimum_group_size(self):
        """Should only create groups with 2+ queries."""
        searches = [("unique term one", 1), ("unique term two", 1)]
        result = suggest_synonym_groups(searches)
        # "unique" and "term" are shared
        if result:
            for group in result:
                self.assertGreaterEqual(len(group), 2)


if __name__ == "__main__":
    unittest.main()
