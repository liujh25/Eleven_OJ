from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

import oj.ai_tasks
from frontend.client import APIError, OJClient
from oj.ai_tasks import AIProviderError, _chat, _completion_url, _normalize_problem_units
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


def test_ai_problem_limit_units_are_normalized():
    assert _normalize_problem_units({"time_limit": 1000, "memory_limit": 128}) == {
        "time_limit": 1.0,
        "memory_limit": 128,
    }
    assert _normalize_problem_units(
        {"time_limit": 3000, "memory_limit": 128 * 1024 * 1024}
    ) == {"time_limit": 3.0, "memory_limit": 128}


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


async def test_deepseek_request_disables_default_thinking(monkeypatch):
    captured: dict = {}

    def answer(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"problem": {}}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    config = AIConfig(
        user_id="deepseek-test",
        provider_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        encrypted_api_key=encrypt_secret("secret"),
    )
    monkeypatch.setattr(oj.ai_tasks, "_json_content", lambda content: {"ok": True})
    result, usage = await _chat(
        config,
        [{"role": "user", "content": "test"}],
        transport=httpx.MockTransport(answer),
    )
    assert result == {"ok": True}
    assert usage == {"prompt_tokens": 3, "completion_tokens": 2}
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["max_tokens"] == 24_000


async def test_invalid_provider_json_is_retried_and_usage_is_aggregated():
    calls = 0

    def answer(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = '{"value": Array.from({length: 10})}' if calls == 1 else '{"ok": true}'
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    config = AIConfig(
        user_id="retry-test",
        provider_url="https://provider.example/v1",
        model="model",
        encrypted_api_key=encrypt_secret("secret"),
    )
    result, usage = await _chat(
        config,
        [{"role": "user", "content": "return json"}],
        transport=httpx.MockTransport(answer),
    )
    assert calls == 2
    assert result == {"ok": True}
    assert usage == {"prompt_tokens": 6, "completion_tokens": 4}


async def test_invalid_provider_json_error_keeps_consumed_usage():
    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"value": Array.from([])}'},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            },
        )

    config = AIConfig(
        user_id="failed-usage-test",
        provider_url="https://provider.example/v1",
        model="model",
        encrypted_api_key=encrypt_secret("secret"),
    )
    with pytest.raises(AIProviderError) as caught:
        await _chat(
            config,
            [{"role": "user", "content": "return json"}],
            transport=httpx.MockTransport(answer),
        )
    assert caught.value.input_tokens == 10
    assert caught.value.output_tokens == 14


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


async def test_ai_review_failure_keeps_validated_draft(api, monkeypatch):
    await login(api, "admin", "admintestpassword")
    await api.put(
        "/api/ai/model-config",
        json={"provider_url": "http://fake.test/v1", "model": "fake", "api_key": "secret"},
    )
    calls = 0

    async def fake_chat(config, messages):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise AIProviderError("review output was truncated")
        return PROBLEM, {"prompt_tokens": 20, "completion_tokens": 10}

    monkeypatch.setattr(oj.ai_tasks, "_chat", fake_chat)
    created = await api.post(
        "/api/ai/problem-tasks/",
        json={"requirement": "设计一道复核异常时仍能保留有效草稿的题目"},
    )
    task = await wait_for_ai(api, created.json()["data"]["task_id"])
    assert task["status"] == "completed"
    assert task["usage"]["total_tokens"] == 30
    assert task["result"]["problem"]["id"] == "ai_sum"
    assert "已保留通过结构校验的草稿" in task["result"]["notes"]


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


def test_ai_console_previews_and_directly_imports_problem():
    imported: list[dict] = []
    task = {
        "task_id": "task-preview",
        "task_type": "authoring",
        "parent_task_id": None,
        "iteration_number": 0,
        "status": "completed",
        "progress": "命题完成，可导入题目表单",
        "usage": {
            "input_tokens": 120,
            "output_tokens": 80,
            "total_tokens": 200,
            "cost": 0.0,
        },
        "error": None,
        "result": PROBLEM,
    }

    def ok(data):
        return httpx.Response(200, json={"code": 200, "msg": "ok", "data": data})

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/api/problems/":
            imported.append(__import__("json").loads(request.content))
            return ok(imported[-1])
        if path == "/api/problems/":
            return ok(imported)
        if path == "/api/problems/ai_sum":
            return ok(PROBLEM["problem"])
        if path == "/api/languages/":
            return ok({"name": ["python"]})
        if path == "/api/submissions/":
            return ok({"total": 0, "submissions": []})
        if path == "/api/ai/problem-tasks/task-preview":
            return ok(task)
        if path == "/api/ai/problem-tasks/":
            return ok([task])
        raise AssertionError(f"unexpected request: {request.method} {path}")

    oj_client = OJClient("http://test")
    oj_client.client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )
    app = AppTest.from_file(Path(__file__).parents[1] / "frontend" / "app.py")
    app.session_state["user"] = {"username": "admin", "user_id": "admin", "role": "admin"}
    app.session_state["nav_page"] = "AI 智能命题"
    app.session_state["ai_task_id"] = "task-preview"
    app.session_state["api"] = oj_client
    app.run(timeout=20)
    assert not app.exception
    assert any("AI 新题可视化" in item.value for item in app.markdown)
    labels = {button.label for button in app.button}
    assert "导入题库并立即打开" in labels
    assert "载入题目管理表单" in labels

    next(button for button in app.button if button.label == "导入题库并立即打开").click().run()
    assert not app.exception
    assert imported == [PROBLEM["problem"]]
    assert app.session_state["nav_page"] == "题目与评测"
    assert app.session_state["workspace_problem"] == "ai_sum"
    assert any("ai_sum · 边界两数之和" in item.value for item in app.subheader)

    imported.clear()
    review_app = AppTest.from_file(Path(__file__).parents[1] / "frontend" / "app.py")
    review_app.session_state["user"] = {
        "username": "admin",
        "user_id": "admin",
        "role": "admin",
    }
    review_app.session_state["nav_page"] = "AI 智能命题"
    review_app.session_state["ai_task_id"] = "task-preview"
    review_app.session_state["api"] = oj_client
    review_app.run(timeout=20)
    next(
        button for button in review_app.button if button.label == "载入题目管理表单"
    ).click().run()
    assert not review_app.exception
    assert review_app.session_state["nav_page"] == "题目与评测"
    assert review_app.session_state["workspace_view"] == "manage"
    assert any(button.label == "保存题目" for button in review_app.button)
    next(button for button in review_app.button if button.label == "保存题目").click().run()
    assert not review_app.exception
    assert imported == [PROBLEM["problem"]]
    assert review_app.session_state["workspace_view"] == "judge"


def test_problem_library_exposes_admin_management_actions():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/problems/":
            return httpx.Response(
                200, json={"code": 200, "msg": "ok", "data": [PROBLEM["problem"]]}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    oj_client = OJClient("http://test")
    oj_client.client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )
    app = AppTest.from_file(Path(__file__).parents[1] / "frontend" / "app.py")
    app.session_state["user"] = {"username": "admin", "user_id": "admin", "role": "admin"}
    app.session_state["nav_page"] = "题目与评测"
    app.session_state["workspace_view"] = "library"
    app.session_state["api"] = oj_client
    app.run(timeout=20)
    assert not app.exception
    labels = {button.label for button in app.button}
    assert "＋ 新增题目" in labels
    assert "⚙ 管理题库" in labels
