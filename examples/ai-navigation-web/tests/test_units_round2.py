"""Phase 5 单元补齐: models 校验规则 / learning_paths 推荐-自定义-加载 / auth 边界。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.auth import create_access_token, get_current_user_id, hash_password, verify_password
from src.learning_paths import LearningPathManager
from src.models import (
    AssessmentResult,
    Contribution,
    ContributionCreate,
    LearningPath,
    LearningProgress,
    Stats,
    UserCreate,
)


# ── models ──────────────────────────────────────────────────


class TestModels:
    def test_user_create_valid(self) -> None:
        u = UserCreate(username="abc", email="a@b.c", password="123456")
        assert u.username == "abc"

    def test_user_create_too_short_username(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(username="ab", email="a@b.c", password="123456")

    def test_user_create_short_password(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(username="abcd", email="a@b.c", password="12345")

    def test_assessment_defaults(self) -> None:
        r = AssessmentResult()
        assert r.overall == 0.0 and len(r.model_fields) >= 6

    def test_progress_and_contribution_roundtrip(self) -> None:
        p = LearningProgress(id=1, doc_path="a.md", doc_title="A", status="pending")
        assert p.notes is None
        c = Contribution(id=1, doc_path="a.md", doc_title="A", status="submitted", submitted_at="2026-08-26")
        assert c.reviewed_at is None
        cc = ContributionCreate(doc_path="a.md", doc_title="A", content="x")
        assert cc.content == "x"

    def test_learning_path_and_stats(self) -> None:
        lp = LearningPath(id=1, path_name="p", target_level="L2", estimated_hours=3.5, created_at="t")
        assert lp.target_level == "L2"
        s = Stats()
        assert s.total_users == 0 and s.avg_score == 0.0


# ── learning_paths ──────────────────────────────────────────


class TestLearningPathManager:
    def _mgr(self, tmp_path: Path) -> LearningPathManager:
        return LearningPathManager(data_dir=tmp_path)

    def test_list_templates_filter_role(self) -> None:
        mgr = self._mgr(Path("/tmp/nonexistent-lp"))
        all_t = mgr.list_templates()
        assert all_t
        fe = mgr.list_templates(role="frontend")
        assert all(t.role in ("frontend", "any") for t in fe)

    @pytest.mark.parametrize(
        ("cur", "target", "expected_nonempty"),
        [("L0", "L2", True), ("L4", "L4", False), ("XX", "L1", False)],
    )
    def test_recommend_path(self, cur: str, target: str, expected_nonempty: bool) -> None:
        mgr = self._mgr(Path("/tmp/nonexistent-lp"))
        rec = mgr.recommend_path(cur, target)
        assert bool(rec) == expected_nonempty

    def test_create_custom_and_reload(self, tmp_path: Path) -> None:
        mgr = self._mgr(tmp_path)
        steps = [{"step_id": "s1", "title": "s1", "description": "d1", "doc_path": "a.md", "estimated_hours": 1.0}]
        template = mgr.create_custom_path("custom-x", "Custom X", "desc", steps)
        assert template.name == "Custom X"
        assert (tmp_path / "custom-x.json").exists()

        names = [p.name for p in mgr.get_all_paths()]
        assert "Custom X" in names


# ── auth ────────────────────────────────────────────────────


class TestAuth:
    def test_hash_verify_roundtrip(self) -> None:
        h = hash_password("secret123")
        assert verify_password("secret123", h)
        assert not verify_password("wrong", h)

    def test_token_roundtrip(self) -> None:
        token = create_access_token({"sub": "42"})
        assert isinstance(token, str) and token.count(".") == 2  # JWT 三段

    def test_get_current_user_id_invalid_cookie(self) -> None:
        from types import SimpleNamespace

        request = SimpleNamespace(cookies={"access_token": "bad.token.value"})
        assert get_current_user_id(request) is None

    def test_get_current_user_id_missing_cookie(self) -> None:
        from types import SimpleNamespace

        request = SimpleNamespace(cookies={})
        assert get_current_user_id(request) is None
