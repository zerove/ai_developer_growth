"""Tests for Personalized Mentor."""

import tempfile
from pathlib import Path

from src.personalized_mentor import (
    DIMENSION_LABELS,
    Dimension,
    Level,
    PersonalizedMentor,
)


class TestPersonalizedMentor:
    def setup_method(self):
        self.mentor = PersonalizedMentor()

    def test_create_plan_basic(self):
        plan = self.mentor.create_plan(
            name="Test User",
            scores={
                "product": 1,
                "architecture": 2,
                "ai_collaboration": 3,
                "engineering": 1,
                "learning": 2,
            },
        )
        assert plan.user_name == "Test User"
        assert plan.overall_level == Level.L1  # average of 1,2,3,1,2 = 1.8 → L1
        assert len(plan.assessments) == 5

    def test_create_plan_all_l0(self):
        plan = self.mentor.create_plan(
            name="Beginner",
            scores={
                "product": 0,
                "architecture": 0,
                "ai_collaboration": 0,
                "engineering": 0,
                "learning": 0,
            },
        )
        assert plan.overall_level == Level.L0
        assert plan.weakest_dimension in DIMENSION_LABELS

    def test_create_plan_all_l4(self):
        plan = self.mentor.create_plan(
            name="Expert",
            scores={
                "product": 4,
                "architecture": 4,
                "ai_collaboration": 4,
                "engineering": 4,
                "learning": 4,
            },
        )
        assert plan.overall_level == Level.L4

    def test_weakest_and_strongest(self):
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": 1,
                "architecture": 3,
                "ai_collaboration": 2,
                "engineering": 4,
                "learning": 0,
            },
        )
        assert plan.weakest_dimension == Dimension.LEARNING
        assert plan.strongest_dimension == Dimension.ENGINEERING

    def test_priority_actions_focus_on_weakest(self):
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": 0,
                "architecture": 2,
                "ai_collaboration": 2,
                "engineering": 2,
                "learning": 2,
            },
        )
        assert len(plan.priority_actions) > 0
        # Should mention the weakest dimension
        actions_text = " ".join(plan.priority_actions)
        assert "问题定义" in actions_text or "L0" in actions_text

    def test_assessments_have_resources(self):
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": 1,
                "architecture": 1,
                "ai_collaboration": 1,
                "engineering": 1,
                "learning": 1,
            },
        )
        # At least some assessments should have resources
        total_resources = sum(len(a.recommended_resources) for a in plan.assessments)
        assert total_resources > 0

    def test_to_dict(self):
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": 1,
                "architecture": 2,
                "ai_collaboration": 3,
                "engineering": 1,
                "learning": 2,
            },
        )
        d = plan.to_dict()
        assert d["user_name"] == "Test"
        assert "overall_level" in d
        assert "assessments" in d
        assert len(d["assessments"]) == 5

    def test_export_plan(self):
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": 1,
                "architecture": 2,
                "ai_collaboration": 3,
                "engineering": 1,
                "learning": 2,
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            self.mentor.export_plan(plan, path)
            assert path.exists()
            import json

            data = json.loads(path.read_text())
            assert data["user_name"] == "Test"

    def test_estimated_weeks(self):
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": 0,
                "architecture": 0,
                "ai_collaboration": 0,
                "engineering": 0,
                "learning": 0,
            },
        )
        # 5 dimensions with gaps = 5 * 3 = 15 weeks
        assert plan.estimated_weeks > 0

    def test_level_clamping(self):
        # Scores outside 0-4 range should be clamped
        plan = self.mentor.create_plan(
            name="Test",
            scores={
                "product": -1,
                "architecture": 10,
                "ai_collaboration": 5,
                "engineering": 2,
                "learning": 3,
            },
        )
        for a in plan.assessments:
            assert Level.L0 <= a.current_level <= Level.L4
