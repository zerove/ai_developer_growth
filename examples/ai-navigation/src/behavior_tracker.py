"""
User Behavior Tracking for AI Navigation

Tracks user interactions to improve recommendations:
- Search queries
- Document views
- Time spent
- Feedback signals
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SearchEvent:
    """Search query event."""

    query: str
    results_count: int
    clicked_doc_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ViewEvent:
    """Document view event."""

    doc_id: str
    duration_seconds: float
    scroll_depth: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FeedbackEvent:
    """User feedback event."""

    doc_id: str
    rating: int  # 1-5
    helpful: bool
    comment: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class UserProfile:
    """User behavior profile."""

    user_id: str
    searches: list[SearchEvent] = field(default_factory=list)
    views: list[ViewEvent] = field(default_factory=list)
    feedback: list[FeedbackEvent] = field(default_factory=list)
    interests: dict[str, float] = field(default_factory=dict)  # category -> score

    def update_interests(self, category: str, score: float):
        """Update interest scores based on behavior."""
        if category in self.interests:
            # Exponential moving average
            self.interests[category] = 0.7 * self.interests[category] + 0.3 * score
        else:
            self.interests[category] = score


class BehaviorTracker:
    """
    Tracks and analyzes user behavior.
    """

    def __init__(self, storage_path: Path | None = None):
        """
        Initialize behavior tracker.

        Args:
            storage_path: Path to store behavior data
        """
        self.storage_path = storage_path
        self.profiles: dict[str, UserProfile] = {}
        self._load_profiles()

    def _load_profiles(self):
        """Load profiles from storage."""
        if self.storage_path and self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for user_id, profile_data in data.items():
                    profile = UserProfile(user_id=user_id)
                    profile.interests = profile_data.get("interests", {})
                    self.profiles[user_id] = profile
            except Exception:
                pass

    def _save_profiles(self):
        """Save profiles to storage."""
        if self.storage_path:
            data = {}
            for user_id, profile in self.profiles.items():
                data[user_id] = {"interests": profile.interests}
            self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def track_search(self, user_id: str, query: str, results_count: int, clicked_doc_id: str | None = None):
        """Track a search event."""
        profile = self._get_or_create_profile(user_id)
        event = SearchEvent(query=query, results_count=results_count, clicked_doc_id=clicked_doc_id)
        profile.searches.append(event)
        self._save_profiles()

    def track_view(self, user_id: str, doc_id: str, duration_seconds: float, scroll_depth: float = 0.0):
        """Track a document view event."""
        profile = self._get_or_create_profile(user_id)
        event = ViewEvent(doc_id=doc_id, duration_seconds=duration_seconds, scroll_depth=scroll_depth)
        profile.views.append(event)
        self._save_profiles()

    def track_feedback(self, user_id: str, doc_id: str, rating: int, helpful: bool, comment: str | None = None):
        """Track user feedback."""
        profile = self._get_or_create_profile(user_id)
        event = FeedbackEvent(doc_id=doc_id, rating=rating, helpful=helpful, comment=comment)
        profile.feedback.append(event)
        self._save_profiles()

    def _get_or_create_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile."""
        if user_id not in self.profiles:
            self.profiles[user_id] = UserProfile(user_id=user_id)
        return self.profiles[user_id]

    def get_user_interests(self, user_id: str) -> dict[str, float]:
        """Get user interest scores by category."""
        profile = self._get_or_create_profile(user_id)

        # Calculate interests from behavior
        interests = defaultdict(float)

        # From views
        for view in profile.views:
            # Extract category from doc_id (simplified)
            category = view.doc_id.split("/")[0] if "/" in view.doc_id else "general"
            # Weight by duration
            interests[category] += min(view.duration_seconds / 60.0, 1.0)

        # From feedback
        for fb in profile.feedback:
            category = fb.doc_id.split("/")[0] if "/" in fb.doc_id else "general"
            if fb.helpful:
                interests[category] += 0.5
            interests[category] += fb.rating / 5.0

        # Normalize
        max_score = max(interests.values()) if interests else 1.0
        return {k: v / max_score for k, v in interests.items()}

    def get_popular_documents(self, top_k: int = 10) -> list[dict]:
        """Get most popular documents based on views and feedback."""
        doc_stats = defaultdict(lambda: {"views": 0, "total_rating": 0, "count": 0})

        # Count views
        for profile in self.profiles.values():
            for view in profile.views:
                doc_stats[view.doc_id]["views"] += 1

        # Count ratings
        for profile in self.profiles.values():
            for fb in profile.feedback:
                doc_stats[fb.doc_id]["total_rating"] += fb.rating
                doc_stats[fb.doc_id]["count"] += 1

        # Calculate popularity score
        popular = []
        for doc_id, stats in doc_stats.items():
            avg_rating = stats["total_rating"] / stats["count"] if stats["count"] > 0 else 0
            score = stats["views"] * 0.6 + avg_rating * 0.4
            popular.append({"doc_id": doc_id, "views": stats["views"], "avg_rating": avg_rating, "score": score})

        # Sort by score
        popular.sort(key=lambda x: x["score"], reverse=True)
        return popular[:top_k]

    def get_trending_queries(self, days: int = 7, top_k: int = 10) -> list[dict]:
        """Get trending search queries."""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        query_counts = defaultdict(int)

        for profile in self.profiles.values():
            for search in profile.searches:
                try:
                    search_time = datetime.fromisoformat(search.timestamp)
                    if search_time > cutoff:
                        query_counts[search.query.lower()] += 1
                except Exception:
                    pass

        # Sort by count
        trending = [{"query": query, "count": count} for query, count in query_counts.items()]
        trending.sort(key=lambda x: x["count"], reverse=True)

        return trending[:top_k]

    def get_stats(self) -> dict:
        """Get overall statistics."""
        total_searches = sum(len(p.searches) for p in self.profiles.values())
        total_views = sum(len(p.views) for p in self.profiles.values())
        total_feedback = sum(len(p.feedback) for p in self.profiles.values())

        return {
            "total_users": len(self.profiles),
            "total_searches": total_searches,
            "total_views": total_views,
            "total_feedback": total_feedback,
        }
