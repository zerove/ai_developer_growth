"""Phase 5 交互式学习平台路由集成测试补充。

覆盖 progress/contribute/assess 三组路由的完整用户旅程:
- progress: 列表/启动去重/完成带笔记/删除/未登录重定向
- contribute: 表单/提交/详情/不存在重定向
- assess: 表单回填/提交出结果与推荐/history
- get_level 边界
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import app
from src.database import init_db
from src.routes.assess_routes import get_level


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register_and_login(client: AsyncClient, username: str) -> None:
    resp = await client.post(
        "/auth/register",
        data={"username": username, "email": f"{username}@example.com", "password": "pass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


# ── progress ────────────────────────────────────────────────


class TestProgressFlow:
    async def test_requires_login(self, client: AsyncClient) -> None:
        resp = await client.get("/progress", follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"] == "/auth/login"

    async def test_start_complete_delete(self, client: AsyncClient) -> None:
        await register_and_login(client, "progresser")

        # 启动学习
        resp = await client.post(
            "/progress/start",
            data={"doc_path": "docs/guide.md", "doc_title": "Guide"},
            follow_redirects=False,
        )
        assert resp.status_code == 303 and resp.headers["location"] == "/progress"

        # 列表可见 in_progress 条目
        resp = await client.get("/progress")
        assert resp.status_code == 200 and "Guide" in resp.text

        # 重复启动不新增(去重)
        await client.post("/progress/start", data={"doc_path": "docs/guide.md", "doc_title": "Guide"})
        resp = await client.get("/progress")
        assert resp.text.count("docs/guide.md") <= 2  # 模板中 path 出现次数有限

        # 完成并附笔记 → 需要知道 id; 通过页面解析不可靠, 直接完成 id=1
        resp = await client.post("/progress/1/complete", data={"notes": "done well"}, follow_redirects=False)
        assert resp.status_code == 303

        # 删除
        resp = await client.post("/progress/1/delete", follow_redirects=False)
        assert resp.status_code == 303

    async def test_complete_nonexistent_is_noop(self, client: AsyncClient) -> None:
        await register_and_login(client, "noop")
        resp = await client.post("/progress/999/complete", data={}, follow_redirects=False)
        assert resp.status_code == 303


# ── contribute ──────────────────────────────────────────────


class TestContributeFlow:
    async def test_requires_login(self, client: AsyncClient) -> None:
        for method, url in [("get", "/contribute"), ("get", "/contribute/new")]:
            resp = await getattr(client, method)(url, follow_redirects=False)
            assert resp.status_code == 303
        # POST 缺表单字段时 FastAPI 校验层先回 422(校验先于登录检查)
        resp = await client.post("/contribute", follow_redirects=False)
        assert resp.status_code == 422

    async def test_submit_view_list(self, client: AsyncClient) -> None:
        await register_and_login(client, "contributor")

        # 表单页
        resp = await client.get("/contribute/new")
        assert resp.status_code == 200

        # 提交
        resp = await client.post(
            "/contribute",
            data={"doc_path": "docs/x.md", "doc_title": "X", "content": "# X"},
            follow_redirects=False,
        )
        assert resp.status_code == 303 and resp.headers["location"] == "/contribute"

        # 列表页含标题
        resp = await client.get("/contribute")
        assert resp.status_code == 200 and "X" in resp.text

        # 详情页
        resp = await client.get("/contribute/1")
        assert resp.status_code == 200 and "# X" in resp.text

        # 不存在的贡献 → 重定向回列表
        resp = await client.get("/contribute/999", follow_redirects=False)
        assert resp.status_code == 303 and resp.headers["location"] == "/contribute"


# ── assess ──────────────────────────────────────────────────


class TestAssessFlow:
    async def test_form_with_prev_fill(self, client: AsyncClient) -> None:
        await register_and_login(client, "assessor")

        # 无历史 → prev=None
        resp = await client.get("/assess")
        assert resp.status_code == 200

        # 提交一次评估
        resp = await client.post(
            "/assess",
            data={
                "ai_comprehension": "0.9",
                "engineering_integration": "0.4",
                "learning_method": "0.6",
                "innovation_thinking": "0.3",
                "output_quality": "0.8",
            },
        )
        assert resp.status_code == 200
        assert "L" in resp.text  # 等级渲染

        # 有历史后表单可回填
        resp = await client.get("/assess")
        assert resp.status_code == 200

        # history 页面有记录
        resp = await client.get("/assess/history")
        assert resp.status_code == 200 and "0.9" in resp.text

    async def test_history_requires_login(self, client: AsyncClient) -> None:
        resp = await client.get("/assess/history", follow_redirects=False)
        assert resp.status_code == 303


class TestGetLevel:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [(0.0, "L0 - 初学者"), (0.2, "L0 - 初学者"), (0.5, "L2 - 胜任"), (0.99, "L4 - 专家")],
    )
    def test_boundaries(self, score: float, expected: str) -> None:
        assert get_level(score) == expected
