#!/usr/bin/env python3
"""Tests for analyze_tracking.py"""

import json

from tools.scripts.analyze_tracking import (
    analyze_pageviews,
    analyze_reading_time,
    analyze_searches,
    load_tracking_data,
    suggest_synonym_groups,
)


class TestLoadTrackingData:
    def test_load_valid_json(self, tmp_path):
        data = {"searches": [], "pageviews": [], "reading_time": {}}
        f = tmp_path / "tracking.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        result = load_tracking_data(str(f))
        assert result == data

    def test_load_with_content(self, tmp_path):
        data = {"searches": [{"q": "python", "results": 5, "ts": 1000}]}
        f = tmp_path / "tracking.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        result = load_tracking_data(str(f))
        assert len(result["searches"]) == 1
        assert result["searches"][0]["q"] == "python"


class TestAnalyzeSearches:
    def test_empty_searches(self):
        result = analyze_searches({"searches": []})
        assert result["total"] == 0
        assert result["unique"] == 0
        assert result["top"] == []

    def test_count_queries(self):
        data = {
            "searches": [
                {"q": "python", "results": 5},
                {"q": "python", "results": 3},
                {"q": "rust", "results": 2},
                {"q": "", "results": 0},  # empty query
            ]
        }
        result = analyze_searches(data)
        assert result["total"] == 4
        assert result["unique"] == 2
        # python appears twice
        assert ("python", 2) in result["top"]
        assert ("rust", 1) in result["top"]

    def test_zero_result_queries(self):
        data = {
            "searches": [
                {"q": "kubernetes", "results": 0},
                {"q": "kubernetes", "results": 0},
                {"q": "docker", "results": 0},
                {"q": "python", "results": 5},
            ]
        }
        result = analyze_searches(data)
        assert len(result["zero_result"]) == 2
        assert result["zero_result"][0] == ("kubernetes", 2)

    def test_top_n_limit(self):
        queries = [{"q": f"term{i}", "results": i} for i in range(20)]
        data = {"searches": queries}
        result = analyze_searches(data, top_n=5)
        assert len(result["top"]) <= 5


class TestAnalyzePageviews:
    def test_empty_pageviews(self):
        result = analyze_pageviews({"pageviews": []})
        assert result["total"] == 0
        assert result["top"] == []

    def test_count_pages(self):
        data = {
            "pageviews": [
                {"page": "/docs/guide/"},
                {"page": "/docs/guide/"},
                {"page": "/docs/api/"},
            ]
        }
        result = analyze_pageviews(data)
        assert result["total"] == 3
        assert result["unique"] == 2
        assert ("/docs/guide/", 2) in result["top"]


class TestAnalyzeReadingTime:
    def test_empty_reading_time(self):
        result = analyze_reading_time({"reading_time": {}})
        assert result["total_seconds"] == 0

    def test_total_and_top(self):
        data = {
            "reading_time": {
                "/guide/": 300,
                "/api/": 120,
                "/tutorial/": 600,
            }
        }
        result = analyze_reading_time(data)
        assert result["total_seconds"] == 1020
        assert result["total_minutes"] == 17.0
        assert result["top"][0] == ("/tutorial/", 600)


class TestSuggestSynonymGroups:
    def test_empty(self):
        assert suggest_synonym_groups([]) == []

    def test_prefix_match(self):
        searches = [("python tutorial", 5), ("python guide", 3), ("rust tutorial", 2)]
        groups = suggest_synonym_groups(searches)
        # python tutorial and python guide share "python"
        assert len(groups) >= 1

    def test_no_matches(self):
        searches = [("python", 5), ("rust", 3)]
        groups = suggest_synonym_groups(searches)
        assert groups == []
