import os

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import app
from src.database import DB_PATH, init_db


@pytest.fixture(autouse=True)
async def setup_db():
    # Remove old DB and reinitialize for each test
    if DB_PATH.exists():
        os.remove(DB_PATH)
    await init_db()
    yield
    if DB_PATH.exists():
        os.remove(DB_PATH)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
