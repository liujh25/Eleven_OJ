from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from oj.config import get_settings
from oj.crypto import decrypt_secret
from oj.db import SessionFactory
from oj.models import AIConfig, AITask, Problem
from oj.schemas import ProblemBody

_tasks: dict[str, asyncio.Task] = {}


def _json_content(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    else:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


async def _update(task_id: str, **values: Any) -> None:
    async with SessionFactory() as db:
        task = await db.get(AITask, task_id)
        if task is not None:
            for key, value in values.items():
                setattr(task, key, value)
            await db.commit()


async def _chat(config: AIConfig, messages: list[dict[str, str]]) -> tuple[dict, dict]:
    headers = {
        "Authorization": f"Bearer {decrypt_secret(config.encrypted_api_key)}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.25,
        "response_format": {"type": "json_object"},
    }
    timeout = httpx.Timeout(get_settings().ai_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.post(
            f"{config.provider_url.rstrip('/')}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        body = response.json()
    content = body["choices"][0]["message"]["content"]
    return _json_content(content), body.get("usage") or {}


def _usage(usage: dict) -> tuple[int, int]:
    return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def _cost(config: AIConfig, input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens / config.price_unit * config.input_price
        + output_tokens / config.price_unit * config.output_price,
        8,
    )


async def run_ai_task(task_id: str) -> None:
    try:
        async with SessionFactory() as db:
            task = await db.get(AITask, task_id)
            if task is None:
                return
            config = await db.get(AIConfig, task.user_id)
            reference = await db.get(Problem, task.problem_id) if task.problem_id else None
            if config is None:
                raise ValueError("model configuration is required")
            requirement = task.requirement
            reference_data = None
            if reference:
                reference_data = {
                    key: getattr(reference, key)
                    for key in (
                        "id",
                        "title",
                        "description",
                        "input_description",
                        "output_description",
                        "samples",
                        "constraints",
                        "testcases",
                        "hint",
                        "source",
                        "tags",
                        "time_limit",
                        "memory_limit",
                        "author",
                        "difficulty",
                    )
                }
        await _update(task_id, status="running", progress="正在分析知识点与难度要求")
        system = (
            "你是程序设计课程命题专家。只返回 JSON。设计可直接导入 OJ 的题目，"
            "每个测试点必须给出确定的 input/output，覆盖普通、边界、极端和易错情况。"
            "顶层字段必须为 problem、coverage、notes。problem 严格包含 id,title,description,"
            "input_description,output_description,samples,constraints,testcases,hint,source,tags,"
            "time_limit,memory_limit,author,difficulty。samples/testcases 是 input/output 字符串列表。"
        )
        prompt = f"命题需求：{requirement}\n已有题目（可为空）：{json.dumps(reference_data, ensure_ascii=False)}"
        draft, first_usage = await _chat(config, [{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        in_tokens, out_tokens = _usage(first_usage)
        await _update(
            task_id,
            progress="正在检查边界条件与测试点区分度",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost=_cost(config, in_tokens, out_tokens),
        )
        critique_prompt = (
            "复核并改进以下题目。确保满足原始需求、字段完整、样例正确，测试点覆盖零值、"
            "最小值、最大值、重复值等适用边界，并能区分常见错误和低效算法。只返回同结构 JSON。\n"
            f"原始需求：{requirement}\n草稿：{json.dumps(draft, ensure_ascii=False)}"
        )
        final, second_usage = await _chat(
            config,
            [{"role": "system", "content": system}, {"role": "user", "content": critique_prompt}],
        )
        second_in, second_out = _usage(second_usage)
        in_tokens += second_in
        out_tokens += second_out
        await _update(task_id, progress="正在校验题目结构与导入兼容性")
        validated = ProblemBody.model_validate(final.get("problem"))
        result = {
            "problem": validated.model_dump(),
            "coverage": final.get("coverage", []),
            "notes": final.get("notes", ""),
        }
        await _update(
            task_id,
            status="completed",
            progress="命题完成，可导入题目表单",
            result=result,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost=_cost(config, in_tokens, out_tokens),
            error=None,
        )
    except asyncio.CancelledError:
        await _update(task_id, status="cancelled", progress="任务已中断", error=None)
        raise
    except Exception as exc:
        message = str(exc)
        message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message)
        await _update(task_id, status="failed", progress="命题失败", error=message[:500])
    finally:
        _tasks.pop(task_id, None)


def schedule_ai_task(task_id: str) -> None:
    task = asyncio.create_task(run_ai_task(task_id))
    _tasks[task_id] = task


def cancel_ai_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True


async def cancel_all_ai_tasks() -> None:
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
