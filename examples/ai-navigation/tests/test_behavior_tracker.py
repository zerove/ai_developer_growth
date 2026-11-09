#!/usr/bin/env python3
"""Tests for behavior tracking and collaborative filtering."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.behavior_tracker import (
    BehaviorTracker,
    CollaborativeFilter,
    FeedbackEvent,
    SearchEvent,
    UserProfile,
    ViewEvent,
)


class TestEvents:
    def test_search_event_defaults(self):
        event = SearchEvent(query="rag", results_count=3)
        assert event.clicked_doc_id is None
        assert isinstance(event.timestamp, str) and event.timestamp

    def test_view_event_defaults(self):
        event = ViewEvent(doc_id="docs/a.md", duration_seconds=30.0)
        assert event.scroll_depth == 0.0
        assert event.timestamp

    def test_feedback_event_defaults(self):
        event = FeedbackEvent(doc_id="docs/a.md", rating=4, helpful=True)
        assert event.comment is None
        assert event.timestamp


class TestUserProfile:
    def test_new_interest_is_assigned(self):
        profile = UserProfile(user_id="u1")
        profile.update_interests("rag", 0.8)
        assert profile.interests == {"rag": 0.8}

    def test_existing_interest_uses_ema(self):
        profile = UserProfile(user_id="u1", interests={"rag": 1.0})
        profile.update_interests("rag", 0.0)
        assert profile.interests["rag"] == 0.7


class TestBehaviorTracker:
    def test_track_search(self):
        tracker = BehaviorTracker()
        tracker.track_search("u1", "rag", 5, clicked_doc_id="docs/a.md")

        event = tracker.profiles["u1"].searches[0]
        assert event.query == "rag"
        assert event.results_count == 5
        assert event.clicked_doc_id == "docs/a.md"

    def test_track_view(self):
        tracker = BehaviorTracker()
        tracker.track_view("u1", "docs/a.md", 42.0, scroll_depth=0.75)

        event = tracker.profiles["u1"].views[0]
        assert event.doc_id == "docs/a.md"
        assert event.duration_seconds == 42.0
        assert event.scroll_depth == 0.75

    def test_track_feedback(self):
        tracker = BehaviorTracker()
        tracker.track_feedback("u1", "docs/a.md", 5, True, comment="great")

        event = tracker.profiles["u1"].feedback[0]
        assert event.rating == 5
        assert event.helpful is True
        assert event.comment == "great"

    def test_save_and_load_profiles(self, tmp_path: Path):
        storage = tmp_path / "behavior.json"
        tracker = BehaviorTracker(storage_path=storage)
        tracker.profiles["u1"] = UserProfile(user_id="u1", interests={"rag": 0.9})
        tracker._save_profiles()

        reloaded = BehaviorTracker(storage_path=storage)
        assert reloaded.profiles["u1"].interests == {"rag": 0.9}

    def test_load_malformed_storage_is_ignored(self, tmp_path: Path):
        storage = tmp_path / "behavior.json"
        storage.write_text("not-json", encoding="utf-8")

        tracker = BehaviorTracker(storage_path=storage)

        assert tracker.profiles == {}

    def test_save_without_storage_is_noop(self):
        tracker = BehaviorTracker()
        tracker._save_profiles()  # 不得抛异常

    def test_get_user_interests_from_views(self):
        tracker = BehaviorTracker()
        tracker.track_view("u1", "docs/a.md", 30.0)
        tracker.track_view("u1", "docs/a.md", 300.0)  # duration 被截断为 1.0

        interests = tracker.get_user_interests("u1")

        assert interests == {"docs": 1.0}

    def test_get_user_interests_from_feedback(self):
        tracker = BehaviorTracker()
        tracker.track_feedback("u1", "guides/a.md", 5, True)
        tracker.track_feedback("u1", "general", 2, False)

        interests = tracker.get_user_interests("u1")

        # guides: 0.5 + 1.0 = 1.5 (max), general: 0.4
        assert interests["guides"] == 1.0
        assert interests["general"] == 0.4 / 1.5

    def test_get_user_interests_zero_signal_returns_empty(self):
        tracker = BehaviorTracker()
        tracker.track_view("u1", "docs/a.md", 0.0)

        assert tracker.get_user_interests("u1") == {}

    def test_get_popular_documents_ranking(self):
        tracker = BehaviorTracker()
        for _ in range(3):
            tracker.track_view("u1", "docs/a.md", 5.0)
        tracker.track_view("u2", "docs/b.md", 5.0)
        tracker.track_feedback("u2", "docs/b.md", 5, True)

        popular = tracker.get_popular_documents(top_k=2)

        # b: 1 view * 0.6 + 5.0 * 0.4 = 2.6；a: 3 views * 0.6 + 0 = 1.8
        assert popular[0]["doc_id"] == "docs/b.md"
        assert popular[0]["avg_rating"] == 5.0
        assert popular[1]["doc_id"] == "docs/a.md"
        assert popular[1]["views"] == 3

    def test_get_trending_queries_filters_and_normalizes(self):
        tracker = BehaviorTracker()
        now = datetime.now()
        old = now - timedelta(days=30)
        tracker.profiles["u1"] = UserProfile(
            user_id="u1",
            searches=[
                SearchEvent(query="AI", results_count=1, timestamp=now.isoformat()),
                SearchEvent(query="ai", results_count=1, timestamp=now.isoformat()),
                SearchEvent(query="old", results_count=1, timestamp=old.isoformat()),
                SearchEvent(query="broken", results_count=1, timestamp="not-a-time"),
            ],
        )

        trending = tracker.get_trending_queries(days=7, top_k=10)

        assert trending == [{"query": "ai", "count": 2}]

    def test_get_stats(self):
        tracker = BehaviorTracker()
        tracker.track_search("u1", "rag", 1)
        tracker.track_view("u1", "docs/a.md", 10.0)
        tracker.track_feedback("u1", "docs/a.md", 4, True)
        tracker.track_view("u2", "docs/b.md", 10.0)

        assert tracker.get_stats() == {
            "total_users": 2,
            "total_searches": 1,
            "total_views": 2,
            "total_feedback": 1,
        }


class TestCollaborativeFilter:
    @staticmethod
    def _tracker() -> BehaviorTracker:
        tracker = BehaviorTracker()
        tracker.profiles["u1"] = UserProfile(
            user_id="u1",
            views=[ViewEvent(doc_id="docs/a.md", duration_seconds=60.0)],
        )
        tracker.profiles["u2"] = UserProfile(
            user_id="u2",
            views=[
                ViewEvent(doc_id="docs/a.md", duration_seconds=60.0),
                ViewEvent(doc_id="docs/b.md", duration_seconds=60.0),
            ],
            feedback=[FeedbackEvent(doc_id="docs/c.md", rating=5, helpful=True)],
        )
        return tracker

    def test_unknown_user_gets_no_recommendations(self):
        flt = CollaborativeFilter(BehaviorTracker())
        assert flt.get_recommendations("nobody") == []

    def test_recommendations_from_similar_user(self):
        flt = CollaborativeFilter(self._tracker())

        recommendations = flt.get_recommendations("u1", top_k=2)

        by_doc = {r["doc_id"]: r for r in recommendations}
        assert set(by_doc) == {"docs/b.md", "docs/c.md"}
        assert "docs/a.md" not in by_doc  # 已看过的不再推荐
        assert by_doc["docs/b.md"]["score"] == 0.5  # Jaccard 0.5 * duration 1.0
        assert by_doc["docs/c.md"]["score"] == 0.5  # Jaccard 0.5 * rating 5/5

    def test_find_similar_users_respects_threshold_and_order(self):
        tracker = self._tracker()
        tracker.profiles["u3"] = UserProfile(
            user_id="u3",
            views=[
                ViewEvent(doc_id="docs/a.md", duration_seconds=1.0),
                ViewEvent(doc_id="docs/b.md", duration_seconds=1.0),
            ],
        )
        flt = CollaborativeFilter(tracker)

        similar = flt._find_similar_users("u1", {"docs/a.md"})

        # u2 与 u3 的 Jaccard 都为 0.5，均高于 0.1
        assert {user for user, _ in similar} == {"u2", "u3"}
        assert all(score == 0.5 for _, score in similar)

    def test_find_similar_users_skips_when_both_empty(self):
        tracker = BehaviorTracker()
        tracker.profiles["u1"] = UserProfile(user_id="u1")
        tracker.profiles["u2"] = UserProfile(user_id="u2")
        flt = CollaborativeFilter(tracker)

        assert flt._find_similar_users("u1", set()) == []

    def test_similar_documents_requires_viewers(self):
        flt = CollaborativeFilter(BehaviorTracker())
        assert flt.get_similar_documents("docs/a.md") == []

    def test_similar_documents_scores_co_views(self):
        tracker = BehaviorTracker()
        tracker.profiles["u1"] = UserProfile(
            user_id="u1",
            views=[
                ViewEvent(doc_id="docs/a.md", duration_seconds=1.0),
                ViewEvent(doc_id="docs/b.md", duration_seconds=1.0),
            ],
        )
        tracker.profiles["u2"] = UserProfile(
            user_id="u2",
            views=[
                ViewEvent(doc_id="docs/a.md", duration_seconds=1.0),
                ViewEvent(doc_id="docs/b.md", duration_seconds=1.0),
                ViewEvent(doc_id="docs/c.md", duration_seconds=1.0),
            ],
        )
        flt = CollaborativeFilter(tracker)

        similar = flt.get_similar_documents("docs/a.md", top_k=2)

        assert similar[0] == {
            "doc_id": "docs/b.md",
            "co_view_count": 2,
            "score": 1.0,
        }
        assert similar[1]["doc_id"] == "docs/c.md"
        assert similar[1]["score"] == 0.5
