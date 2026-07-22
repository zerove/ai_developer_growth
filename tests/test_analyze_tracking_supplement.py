"""Tests for analyze_tracking.py - improve coverage from 52% to 70%+."""
import json
import os
import tempfile
import unittest

from tools.scripts.analyze_tracking import (
    analyze_pageviews,
    analyze_reading_time,
    analyze_searches,
    load_tracking_data,
    suggest_synonym_groups,
)


class TestAnalyzeSearches(unittest.TestCase):
    """Test search analysis functions."""

    def test_empty_searches(self):
        """Empty searches should return zero counts."""
        result = analyze_searches({})
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unique"], 0)
        self.assertEqual(result["top"], [])
        self.assertEqual(result["zero_result"], [])

    def test_single_search(self):
        """Single search should be counted."""
        data = {"searches": [{"q": "python", "results": 5}]}
        result = analyze_searches(data)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["unique"], 1)
        self.assertEqual(result["top"], [("python", 1)])

    def test_duplicate_queries(self):
        """Duplicate queries should be aggregated."""
        data = {"searches": [
            {"q": "python", "results": 5},
            {"q": "python", "results": 3},
            {"q": "rust", "results": 2},
        ]}
        result = analyze_searches(data)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["unique"], 2)
        self.assertEqual(result["top"][0], ("python", 2))

    def test_zero_result_queries(self):
        """Queries with 0 results should be tracked."""
        data = {"searches": [
            {"q": "missing", "results": 0},
            {"q": "found", "results": 5},
            {"q": "missing", "results": 0},
        ]}
        result = analyze_searches(data)
        self.assertEqual(len(result["zero_result"]), 1)
        self.assertEqual(result["zero_result"][0], ("missing", 2))

    def test_empty_query_ignored(self):
        """Empty queries should be ignored."""
        data = {"searches": [
            {"q": "", "results": 0},
            {"q": "  ", "results": 0},
            {"q": "valid", "results": 1},
        ]}
        result = analyze_searches(data)
        self.assertEqual(result["unique"], 1)

    def test_top_n_limit(self):
        """Should respect top_n parameter."""
        data = {"searches": [{"q": f"query{i}", "results": 1} for i in range(20)]}
        result = analyze_searches(data, top_n=5)
        self.assertEqual(len(result["top"]), 5)


class TestAnalyzePageviews(unittest.TestCase):
    """Test pageview analysis functions."""

    def test_empty_pageviews(self):
        """Empty pageviews should return zero counts."""
        result = analyze_pageviews({})
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unique"], 0)
        self.assertEqual(result["top"], [])

    def test_single_pageview(self):
        """Single pageview should be counted."""
        data = {"pageviews": [{"page": "/docs/"}]}
        result = analyze_pageviews(data)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["unique"], 1)

    def test_duplicate_pages(self):
        """Duplicate pages should be aggregated."""
        data = {"pageviews": [
            {"page": "/docs/"},
            {"page": "/docs/"},
            {"page": "/about/"},
        ]}
        result = analyze_pageviews(data)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["unique"], 2)
        self.assertEqual(result["top"][0], ("/docs/", 2))

    def test_top_n_limit(self):
        """Should respect top_n parameter."""
        data = {"pageviews": [{"page": f"/page{i}/"} for i in range(20)]}
        result = analyze_pageviews(data, top_n=5)
        self.assertEqual(len(result["top"]), 5)


class TestAnalyzeReadingTime(unittest.TestCase):
    """Test reading time analysis functions."""

    def test_empty_reading_time(self):
        """Empty reading time should return zero."""
        result = analyze_reading_time({})
        self.assertEqual(result["total_seconds"], 0)
        self.assertEqual(result["top"], [])

    def test_single_page(self):
        """Single page reading time should be counted."""
        data = {"reading_time": {"/docs/": 120}}
        result = analyze_reading_time(data)
        self.assertEqual(result["total_seconds"], 120)
        self.assertEqual(result["total_minutes"], 2.0)

    def test_multiple_pages(self):
        """Multiple pages should be summed and sorted."""
        data = {"reading_time": {
            "/docs/": 300,
            "/about/": 60,
            "/blog/": 180,
        }}
        result = analyze_reading_time(data)
        self.assertEqual(result["total_seconds"], 540)
        self.assertEqual(result["top"][0], ("/docs/", 300))

    def test_top_n_limit(self):
        """Should respect top_n parameter."""
        data = {"reading_time": {f"/page{i}/": i * 10 for i in range(20)}}
        result = analyze_reading_time(data, top_n=5)
        self.assertEqual(len(result["top"]), 5)


class TestSuggestSynonymGroups(unittest.TestCase):
    """Test synonym group suggestion."""

    def test_empty_searches(self):
        """Empty searches should return empty list."""
        result = suggest_synonym_groups([])
        self.assertEqual(result, [])

    def test_no_shared_words(self):
        """Queries with no shared words should not form groups."""
        searches = [("python tutorial", 5), ("rust guide", 3)]
        result = suggest_synonym_groups(searches)
        self.assertEqual(result, [])

    def test_shared_word_group(self):
        """Queries sharing a word should form a group."""
        searches = [
            ("python tutorial", 5),
            ("python guide", 3),
            ("python basics", 2),
        ]
        result = suggest_synonym_groups(searches)
        self.assertGreater(len(result), 0)
        # All should be in the same group
        all_queries = [q for group in result for q in group]
        self.assertIn("python tutorial", all_queries)
        self.assertIn("python guide", all_queries)

    def test_short_words_ignored(self):
        """Words shorter than 3 chars should be ignored."""
        searches = [("a b c", 5), ("a b d", 3)]
        result = suggest_synonym_groups(searches)
        # "a", "b", "c", "d" are all < 3 chars
        self.assertEqual(result, [])

    def test_single_query_no_group(self):
        """Single query should not form a group."""
        searches = [("python tutorial", 5)]
        result = suggest_synonym_groups(searches)
        self.assertEqual(result, [])


class TestLoadTrackingData(unittest.TestCase):
    """Test data loading."""

    def test_load_valid_json(self):
        """Should load valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"searches": [], "pageviews": []}, f)
            f.flush()
            try:
                data = load_tracking_data(f.name)
                self.assertIn("searches", data)
                self.assertIn("pageviews", data)
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
