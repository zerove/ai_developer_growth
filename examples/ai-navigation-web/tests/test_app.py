from httpx import AsyncClient


async def test_home(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "AI Developer Growth" in resp.text


async def test_register_and_login(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "pass123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"

    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "testuser" in resp.text

    resp = await client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 303


async def test_login_page(client: AsyncClient):
    resp = await client.get("/auth/login")
    assert resp.status_code == 200
    assert "Login" in resp.text


async def test_register_page(client: AsyncClient):
    resp = await client.get("/auth/register")
    assert resp.status_code == 200
    assert "Create Account" in resp.text


async def test_assessment_requires_login(client: AsyncClient):
    resp = await client.get("/assess", follow_redirects=False)
    assert resp.status_code == 303


async def test_full_flow(client: AsyncClient):
    await client.post(
        "/auth/register",
        data={
            "username": "flowuser",
            "email": "flow@example.com",
            "password": "pass123",
        },
        follow_redirects=False,
    )

    resp = await client.post(
        "/assess",
        data={
            "ai_comprehension": "70",
            "engineering_integration": "60",
            "learning_method": "80",
            "innovation_thinking": "50",
            "output_quality": "65",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Assessment Result" in resp.text

    resp = await client.get("/progress")
    assert resp.status_code == 200

    resp = await client.get("/contribute")
    assert resp.status_code == 200


async def test_duplicate_register(client: AsyncClient):
    await client.post(
        "/auth/register",
        data={"username": "dupuser", "email": "dup@example.com", "password": "pass123"},
        follow_redirects=False,
    )
    resp = await client.post(
        "/auth/register",
        data={"username": "dupuser", "email": "dup@example.com", "password": "pass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "already exists" in resp.text


async def test_bad_login(client: AsyncClient):
    resp = await client.post(
        "/auth/login",
        data={"username": "nobody", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "Invalid credentials" in resp.text
