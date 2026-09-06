from __future__ import annotations

import json

import httpx
import pytest

from oj.luogu import (
    LuoguProblemNotFound,
    fetch_luogu_problem,
    normalize_luogu_problem_id,
    parse_luogu_problem_page,
)


def luogu_document() -> str:
    context = {
        "data": {
            "problem": {
                "pid": "P1001",
                "name": "A+B Problem",
                "difficulty": 1,
                "contenu": {
                    "name": "A+B Problem",
                    "background": "竞赛入门背景",
                    "description": "输入两个整数并计算结果。",
                    "formatI": "一行两个整数。",
                    "formatO": "输出一个整数。",
                    "hint": "包含负数边界。",
                },
                "samples": [["1 2\n", "3\n"]],
                "limits": {"time": [1000, 2000], "memory": [131072, 262144]},
            }
        }
    }
    return (
        '<html><script id="lentille-context" type="application/json">'
        f"{json.dumps(context)}"
        "</script></html>"
    )


def test_normalize_and_parse_luogu_problem():
    assert normalize_luogu_problem_id(" 1001 ") == "P1001"
    assert normalize_luogu_problem_id("p1001") == "P1001"
    with pytest.raises(ValueError):
        normalize_luogu_problem_id("https://example.com/")
    parsed = parse_luogu_problem_page("P1001", luogu_document())
    assert parsed["problem_id"] == "P1001"
    assert parsed["title"] == "A+B Problem"
    assert parsed["difficulty"] == "入门"
    assert parsed["samples"] == [{"input": "1 2", "output": "3"}]
    assert parsed["time_limit_ms"] == 2000
    assert parsed["memory_limit_kb"] == 262144


async def test_fetch_luogu_problem_uses_fixed_safe_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://www.luogu.com.cn/problem/P1001"
        assert request.headers["user-agent"] == "AsyncOJ-CourseProject/1.0"
        return httpx.Response(200, text=luogu_document())

    result = await fetch_luogu_problem("1001", transport=httpx.MockTransport(handler))
    assert result["url"] == "https://www.luogu.com.cn/problem/P1001"


async def test_fetch_luogu_problem_reports_not_found():
    transport = httpx.MockTransport(lambda _: httpx.Response(404))
    with pytest.raises(LuoguProblemNotFound):
        await fetch_luogu_problem("P99999999", transport=transport)
