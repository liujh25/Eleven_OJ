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

_TEST_STRATEGIES = {
    "basic": "简单测试：覆盖题面样例附近和最常见的正常输入，便于快速定位基础错误",
    "boundary": "边界测试：覆盖最小值、最大值、空/单元素、零值及临界转折点中适用的情况",
    "performance": "性能测试：构造约束上界的合法大规模输入，使未采用目标优化算法的实现超时",
    "corner": "特殊情形：覆盖重复值、有序/逆序、全相同、退化结构等与题目相关的角落情况",
    "overflow": "溢出测试：覆盖中间结果或答案可能越过 32 位整数范围的合法输入",
    "adversarial": "易错对抗测试：针对常见错误算法、下标偏移、贪心误判或状态遗漏设计反例",
    "randomized": "多样性测试：选取具有代表性的混合分布数据，避免测试点结构过于单一",
}


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


def _test_plan_prompt(plan: dict | None) -> str:
    plan = plan or {
        "strategies": ["basic", "boundary", "corner"],
        "target_count": 10,
        "preserve_existing": True,
        "custom_requirements": "",
    }
    strategy_lines = [
        f"- {_TEST_STRATEGIES[strategy]}"
        for strategy in plan.get("strategies", [])
        if strategy in _TEST_STRATEGIES
    ]
    preserve = (
        "保留并复核已有有效测试点" if plan.get("preserve_existing", True) else "可以重建测试点集合"
    )
    custom = plan.get("custom_requirements") or "无"
    return (
        f"测试点目标数量：{plan.get('target_count', 10)}；{preserve}。\n"
        f"测试策略：\n{chr(10).join(strategy_lines)}\n自定义要求：{custom}"
    )


async def run_ai_task(task_id: str) -> None:
    try:
        async with SessionFactory() as db:
            task = await db.get(AITask, task_id)
            if task is None:
                return
            config = await db.get(AIConfig, task.user_id)
            reference = await db.get(Problem, task.problem_id) if task.problem_id else None
            parent = await db.get(AITask, task.parent_task_id) if task.parent_task_id else None
            if config is None:
                raise ValueError("model configuration is required")
            requirement = task.requirement
            task_type = task.task_type
            feedback = task.feedback or ""
            test_plan = task.test_plan
            parent_result = parent.result if parent else None
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
        progress = {
            "iteration": "正在理解改进意见并对比上一版本",
            "test_refinement": "正在分析算法复杂度与测试薄弱点",
        }.get(task_type, "正在分析知识点与难度要求")
        await _update(task_id, status="running", progress=progress)
        system = (
            "你是程序设计课程命题专家。只返回 JSON。设计可直接导入 OJ 的题目，"
            "每个测试点必须给出确定且可以被参考解验证的 input/output；禁止使用省略号、随机占位符"
            "或无法执行的生成器描述。性能测试必须是输入约束内的具体数据，并在 coverage 中说明它"
            "要淘汰的低效复杂度。"
            "顶层字段必须为 problem、coverage、notes。problem 严格包含 id,title,description,"
            "input_description,output_description,samples,constraints,testcases,hint,source,tags,"
            "time_limit,memory_limit,author,difficulty。"
            "samples/testcases 是 input/output 字符串列表。"
        )
        reference_json = json.dumps(reference_data, ensure_ascii=False)
        test_plan_prompt = _test_plan_prompt(test_plan)
        if task_type == "iteration":
            prompt = (
                "请以已有 AI 题目为基线，根据用户改进意见生成完整的新版本。没有被要求修改的字段"
                "应保持稳定，修正后重新核对样例和所有测试点。\n"
                f"原始命题需求：{requirement}\n用户改进意见：{feedback}\n"
                f"上一版本：{json.dumps(parent_result, ensure_ascii=False)}\n{test_plan_prompt}"
            )
        elif task_type == "test_refinement":
            prompt = (
                "请保持已有题目的核心题意、输入输出协议和可见样例稳定，重点重建或补强隐藏测试点。"
                "测试点之间应有清晰分工，输出必须准确；必要时可调整限制使性能测试公平有效。\n"
                f"原始命题需求：{requirement}\n已有题目："
                f"{json.dumps(parent_result, ensure_ascii=False)}\n{test_plan_prompt}"
            )
        else:
            prompt = (
                f"命题需求：{requirement}\n已有题目（可为空）：{reference_json}\n{test_plan_prompt}"
            )
        draft, first_usage = await _chat(
            config, [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        )
        in_tokens, out_tokens = _usage(first_usage)
        await _update(
            task_id,
            progress="正在检查题意一致性、边界覆盖与测试点区分度",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost=_cost(config, in_tokens, out_tokens),
        )
        critique_prompt = (
            "复核并改进以下题目。确保满足原始需求、字段完整、样例正确，测试点覆盖零值、"
            "最小值、最大值、重复值等适用边界，并能区分常见错误和低效算法。严格执行测试策略，"
            "在 coverage 中逐项写明测试类别、覆盖目的和预期淘汰的错误。只返回同结构 JSON。\n"
            f"原始需求：{requirement}\n改进意见：{feedback or '无'}\n{test_plan_prompt}\n"
            f"草稿：{json.dumps(draft, ensure_ascii=False)}"
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
            "version": {
                "task_type": task_type,
                "parent_task_id": task.parent_task_id,
                "iteration_number": task.iteration_number,
            },
            "test_plan": test_plan,
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
