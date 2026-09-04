from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

import oj.ai_tasks
from frontend.client import APIError, OJClient
from tests.conftest import login
from tests.fake_provider import PROBLEM


async def test_ai_progress_usage_and_result(api, monkeypatch):
    admin = await login(api, "admin", "admintestpassword")
    configured = await api.put(
        "/api/ai/model-config",
        json={
            "provider_url": "http://fake.test/v1",
            "model": "fake-model",
            "api_key": "never-log-this-secret",
            "input_price": 1.0,
            "output_price": 2.0,
            "price_unit": 1000,
        },
    )
    assert configured.json()["data"]["api_key_configured"] is True
    assert "never-log" not in configured.text

    async def fake_chat(config, messages):
        await asyncio.sleep(0)
        return PROBLEM, {"prompt_tokens": 120, "completion_tokens": 80}

    monkeypatch.setattr(oj.ai_tasks, "_chat", fake_chat)
    created = await api.post(
        "/api/ai/problem-tasks/",
        json={"requirement": "设计一道包含边界条件的两数之和练习题"},
    )
    task_id = created.json()["data"]["task_id"]
    for _ in range(30):
        task = (await api.get(f"/api/ai/problem-tasks/{task_id}")).json()["data"]
        if task["status"] == "completed":
            break
        await asyncio.sleep(0.02)
    assert task["status"] == "completed"
    assert task["result"]["problem"]["id"] == "ai_sum"
    assert task["usage"] == {
        "input_tokens": 240,
        "output_tokens": 160,
        "total_tokens": 400,
        "cost": 0.56,
        "currency": "USD",
    }
    profile = (await api.get(f"/api/users/{admin['user_id']}")).json()["data"]
    assert profile["ai_problem_count"] == 1


async def test_ai_cancel_really_stops_task(api, monkeypatch):
    await login(api, "admin", "admintestpassword")
    await api.put(
        "/api/ai/model-config",
        json={"provider_url": "http://fake.test/v1", "model": "fake", "api_key": "secret"},
    )

    async def slow_chat(config, messages):
        await asyncio.sleep(30)
        return PROBLEM, {}

    monkeypatch.setattr(oj.ai_tasks, "_chat", slow_chat)
    created = await api.post(
        "/api/ai/problem-tasks/",
        json={"requirement": "设计一道可以随时中断的测试命题任务"},
    )
    task_id = created.json()["data"]["task_id"]
    await asyncio.sleep(0.02)
    cancelled = await api.put(f"/api/ai/problem-tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    await asyncio.sleep(0.05)
    task = (await api.get(f"/api/ai/problem-tasks/{task_id}")).json()["data"]
    assert task["status"] == "cancelled"


def test_frontend_api_client_error_contract():
    def handler(request):
        return httpx.Response(403, json={"code": 403, "msg": "denied", "data": None})

    oj_client = OJClient("http://test")
    oj_client.client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        oj_client.get("/api/users/admin")
    except APIError as exc:
        assert exc.status == 403
        assert str(exc) == "denied"
    else:
        raise AssertionError("APIError was not raised")


def test_streamlit_app_smoke():
    app = AppTest.from_file(Path(__file__).parents[1] / "frontend" / "app.py")
    app.run(timeout=20)
    assert not app.exception
    labels = {button.label for button in app.button}
    assert any("习题与评测" in label for label in labels)
    assert any("登录 / 注册" in label for label in labels)
    assert any("AI 智能命题" in label for label in labels)
