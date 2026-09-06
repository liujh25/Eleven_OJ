from __future__ import annotations

import html
import json
import re
from typing import Any

import httpx

from oj.config import get_settings

LUOGU_BASE_URL = "https://www.luogu.com.cn/problem"
MAX_RESPONSE_BYTES = 2_000_000
_PROBLEM_ID = re.compile(r"^(?:[PBCASUT]\d{1,8}|\d{1,8})$", re.IGNORECASE)
_CONTEXT = re.compile(
    r'<script[^>]+id=["\']lentille-context["\'][^>]*>(?P<payload>.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_DIFFICULTIES = {
    0: "暂无评定",
    1: "入门",
    2: "普及-",
    3: "普及/提高-",
    4: "普及+/提高",
    5: "提高+/省选-",
    6: "省选/NOI-",
    7: "NOI/NOI+/CTSC",
}


class LuoguFetchError(RuntimeError):
    pass


class LuoguProblemNotFound(LuoguFetchError):
    pass


def normalize_luogu_problem_id(value: str) -> str:
    problem_id = value.strip().upper()
    if not _PROBLEM_ID.fullmatch(problem_id):
        raise ValueError("invalid Luogu problem id")
    if problem_id.isdigit():
        problem_id = f"P{problem_id}"
    return problem_id


def _limited_text(value: Any, limit: int) -> str:
    text = html.unescape(str(value or "")).replace("\x00", "").strip()
    return text[:limit]


def _samples(value: Any) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    if not isinstance(value, list):
        return samples
    for item in value[:5]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            sample_input, sample_output = item[0], item[1]
        elif isinstance(item, dict):
            sample_input = item.get("input", "")
            sample_output = item.get("output", "")
        else:
            continue
        samples.append(
            {
                "input": _limited_text(sample_input, 4000),
                "output": _limited_text(sample_output, 4000),
            }
        )
    return samples


def _numeric_max(value: Any) -> int | None:
    if not isinstance(value, list):
        return None
    numbers = [item for item in value if isinstance(item, (int, float)) and item >= 0]
    return int(max(numbers)) if numbers else None


def parse_luogu_problem_page(problem_id: str, document: str) -> dict[str, Any]:
    match = _CONTEXT.search(document)
    if not match:
        raise LuoguFetchError("洛谷页面中未找到题目数据")
    try:
        context = json.loads(match.group("payload"))
        problem = context["data"]["problem"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise LuoguFetchError("洛谷题目数据格式无法解析") from exc
    if not isinstance(problem, dict):
        raise LuoguFetchError("洛谷题目数据格式无法解析")
    content = problem.get("contenu") or problem.get("content") or {}
    if not isinstance(content, dict):
        content = {}
    limits = problem.get("limits") or {}
    time_limits = limits.get("time", []) if isinstance(limits, dict) else []
    memory_limits = limits.get("memory", []) if isinstance(limits, dict) else []
    difficulty_value = problem.get("difficulty")
    difficulty = (
        _DIFFICULTIES.get(difficulty_value, "暂无评定")
        if isinstance(difficulty_value, int)
        else "暂无评定"
    )
    return {
        "provider": "luogu",
        "problem_id": _limited_text(problem.get("pid") or problem_id, 20),
        "url": f"{LUOGU_BASE_URL}/{problem_id}",
        "title": _limited_text(problem.get("name") or content.get("name"), 300),
        "difficulty": difficulty,
        "background": _limited_text(content.get("background"), 5000),
        "description": _limited_text(content.get("description"), 8000),
        "input_description": _limited_text(content.get("formatI"), 4000),
        "output_description": _limited_text(content.get("formatO"), 4000),
        "hint": _limited_text(content.get("hint"), 5000),
        "samples": _samples(problem.get("samples")),
        "time_limit_ms": _numeric_max(time_limits),
        "memory_limit_kb": _numeric_max(memory_limits),
    }


async def fetch_luogu_problem(
    problem_id: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    normalized = normalize_luogu_problem_id(problem_id)
    settings = get_settings()
    headers = {
        "User-Agent": "AsyncOJ-CourseProject/1.0",
        "Accept": "text/html,application/xhtml+xml",
    }
    timeout = httpx.Timeout(settings.luogu_timeout_seconds)
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, transport=transport
        ) as client:
            async with client.stream(
                "GET", f"{LUOGU_BASE_URL}/{normalized}", headers=headers
            ) as response:
                if response.status_code == 404:
                    raise LuoguProblemNotFound(f"洛谷题目 {normalized} 不存在")
                response.raise_for_status()
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > MAX_RESPONSE_BYTES:
                        raise LuoguFetchError("洛谷题目页面过大")
    except LuoguFetchError:
        raise
    except (httpx.HTTPError, TimeoutError) as exc:
        raise LuoguFetchError("暂时无法获取洛谷题目，请稍后重试") from exc
    return parse_luogu_problem_page(normalized, payload.decode("utf-8", errors="replace"))
