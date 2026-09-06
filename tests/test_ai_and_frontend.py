from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

import oj.ai_tasks
from frontend.client import APIError, OJClient
from oj.ai_tasks import AIProviderError, _chat, _completion_url
from oj.crypto import encrypt_secret
from oj.models import AIConfig
from tests.conftest import login
from tests.fake_provider import PROBLEM


def test_openai_compatible_endpoint_normalization():
    assert _completion_url("https://provider.example") == (
        "https://provider.example/v1/chat/completions"
    )
    assert _completion_url("https://provider.example/v1/") == (
        "https://provider.example/v1/chat/completions"
    )
    assert _completion_url("http://localhost:9000/custom/v2") == (
        "http://localhost:9000/custom/v2/chat/completions"
    )


async def test_model_timeout_records_actionable_error():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    config = AIConfig(
        user_id="timeout-test",
        provider_url="https://provider.example",
        model="slow-model",
        encrypted_api_key=encrypt_secret("secret"),
    )
    with pytest.raises(AIProviderError, match="300 秒.*?/v1"):
        await _chat(
            config,
            [{"role": "user", "content": "test"}],
            transport=httpx.MockTransport(timeout),
        )


async def wait_for_ai(api, task_id: str) -> dict:
    for _ in range(50):
        task = (await api.get(f"/api/ai/problem-tasks/{task_id}")).json()["data"]
        if task["status"] in {"completed", "failed", "cancelled"}:
            return task
        await asyncio.sleep(0.02)
    raise AssertionError(f"AI task {task_id} did not finish")


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
    task = await wait_for_ai(api, task_id)
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


async def test_ai_iteration_and_precision_test_plan(api, monkeypatch):
    await login(api, "admin", "admintestpassword")
    await api.put(
        "/api/ai/model-config",
        json={"provider_url": "http://fake.test/v1", "model": "fake", "api_key": "secret"},
    )
    prompts: list[str] = []

    async def fake_chat(config, messages):
        prompts.extend(message["content"] for message in messages)
        await asyncio.sleep(0)
        return PROBLEM, {"prompt_tokens": 10, "completion_tokens": 5}

    monkeypatch.setattr(oj.ai_tasks, "_chat", fake_chat)
    created = await api.post(
        "/api/ai/problem-tasks/",
        json={"requirement": "设计一道能够反复改进并精细配置测试点的算法题"},
    )
    original_id = created.json()["data"]["task_id"]
    assert (await wait_for_ai(api, original_id))["status"] == "completed"

    iteration = await api.post(
        f"/api/ai/problem-tasks/{original_id}/iterations",
        json={
            "feedback": "保持输入格式不变，增加实际场景，并把难度调整为中等",
            "test_plan": {
                "strategies": ["normal", "boundary", "performance"],
                "target_count": 6,
                "case_counts": {"normal": 3, "boundary": 2, "performance": 1},
                "preserve_existing": True,
                "custom_requirements": "普通点覆盖约束中段",
            },
        },
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["data"]["task_id"]
    iterated = await wait_for_ai(api, iteration_id)
    assert iterated["status"] == "completed"
    assert iterated["task_type"] == "iteration"
    assert iterated["parent_task_id"] == original_id
    assert iterated["iteration_number"] == 1
    assert iterated["test_plan"]["case_counts"]["normal"] == 3
    assert iterated["result"]["version"]["task_type"] == "iteration"

    refinement = await api.post(
        f"/api/ai/problem-tasks/{iteration_id}/test-refinements",
        json={
            "test_plan": {
                "strategies": ["basic", "boundary", "performance", "overflow", "adversarial"],
                "target_count": 16,
                "preserve_existing": True,
                "custom_requirements": "性能点需要区分 O(n log n) 与 O(n²)",
            }
        },
    )
    assert refinement.status_code == 200
    refined = await wait_for_ai(api, refinement.json()["data"]["task_id"])
    assert refined["status"] == "completed"
    assert refined["task_type"] == "test_refinement"
    assert refined["parent_task_id"] == iteration_id
    assert refined["iteration_number"] == 2
    assert refined["test_plan"]["target_count"] == 16
    combined_prompts = "\n".join(prompts)
    assert "增加实际场景" in combined_prompts
    assert "普通测试" in combined_prompts
    assert "生成 3 个" in combined_prompts
    assert "性能测试" in combined_prompts
    assert "O(n log n) 与 O(n²)" in combined_prompts


async def test_luogu_reference_authoring(api, monkeypatch):
    await login(api, "admin", "admintestpassword")
    await api.put(
        "/api/ai/model-config",
        json={"provider_url": "http://fake.test/v1", "model": "fake", "api_key": "secret"},
    )
    prompts: list[str] = []

    async def fake_fetch(problem_id: str):
        assert problem_id == "P1001"
        return {
            "provider": "luogu",
            "problem_id": "P1001",
            "url": "https://www.luogu.com.cn/problem/P1001",
            "title": "A+B Problem",
            "difficulty": "入门",
            "background": "竞赛入门背景",
            "description": "输入两个整数并计算结果。",
            "input_description": "一行两个整数。",
            "output_description": "输出一个整数。",
            "hint": "包含负数边界。",
            "samples": [{"input": "1 2", "output": "3"}],
            "time_limit_ms": 1000,
            "memory_limit_kb": 128000,
        }

    async def fake_chat(config, messages):
        prompts.extend(message["content"] for message in messages)
        return PROBLEM, {"prompt_tokens": 10, "completion_tokens": 5}

    monkeypatch.setattr("oj.routers.ai.fetch_luogu_problem", fake_fetch)
    monkeypatch.setattr(oj.ai_tasks, "_chat", fake_chat)
    created = await api.post(
        "/api/ai/luogu-problem-tasks/",
        json={
            "problem_id": "1001",
            "mode": "extension",
            "additional_requirement": "增加多次查询并保持入门难度",
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["reference"]["problem_id"] == "P1001"
    task = await wait_for_ai(api, created.json()["data"]["task_id"])
    assert task["status"] == "completed"
    assert task["task_type"] == "luogu_extension"
    assert task["external_source"] == {
        "provider": "luogu",
        "problem_id": "P1001",
        "url": "https://www.luogu.com.cn/problem/P1001",
        "title": "A+B Problem",
        "difficulty": "入门",
        "mode": "extension",
    }
    assert task["result"]["version"]["external_source"]["problem_id"] == "P1001"
    combined = "\n".join(prompts)
    assert "增加多次查询" in combined
    assert "untrusted_reference_data" in combined
    assert "不得复制" in combined

    invalid = await api.post(
        "/api/ai/luogu-problem-tasks/",
        json={"problem_id": "https://example.com", "mode": "similar"},
    )
    assert invalid.status_code == 400


async def test_ai_iteration_requires_completed_source(api, monkeypatch):
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
        json={"requirement": "设计一道尚未结束且不能直接迭代的测试题"},
    )
    task_id = created.json()["data"]["task_id"]
    response = await api.post(
        f"/api/ai/problem-tasks/{task_id}/iterations",
        json={"feedback": "立即生成下一版"},
    )
    assert response.status_code == 409
    await api.put(f"/api/ai/problem-tasks/{task_id}/cancel")


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
    assert not app.sidebar.radio
    labels = {button.label for button in app.button}
    assert any("习题与评测" in label for label in labels)
    assert any("登录 / 注册" in label for label in labels)
    assert any("AI 智能命题" in label for label in labels)
    next(button for button in app.button if "登录 / 注册" in button.label).click().run()
    assert not app.exception
    assert any(button.label == "← 返回首页" for button in app.button)
    next(button for button in app.button if button.label == "← 返回首页").click().run()
    assert any("习题与评测" in button.label for button in app.button)
