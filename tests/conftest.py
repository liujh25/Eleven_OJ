from __future__ import annotations

import os

import httpx
import pytest

os.environ["OJ_DATABASE_URL"] = "sqlite+aiosqlite:///./tmp/test-oj.db"
os.environ["OJ_DATA_DIR"] = "tmp/test-data"
os.environ["OJ_EXECUTOR_ENABLED"] = "false"
os.environ["OJ_SEED_CURATED_PROBLEMS"] = "false"

from oj.app import app  # noqa: E402
from oj.db import engine, initialize_database  # noqa: E402
from oj.models import Base  # noqa: E402


@pytest.fixture
async def api():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await initialize_database()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def login(client: httpx.AsyncClient, username: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def problem_body(problem_id: str = "sum_2") -> dict:
    return {
        "id": problem_id,
        "title": "两数之和",
        "description": "输入两个整数，输出它们的和。",
        "input_description": "一行两个整数。",
        "output_description": "输出整数和。",
        "samples": [{"input": "1 2\n", "output": "3\n"}],
        "constraints": "-10^9 <= a,b <= 10^9",
        "testcases": [
            {"input": "1 2\n", "output": "3\n"},
            {"input": "-5 5\n", "output": "0\n"},
        ],
        "tags": ["基础", "数学"],
        "time_limit": 1.0,
        "memory_limit": 128,
    }
