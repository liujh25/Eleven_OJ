from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Fake OpenAI-compatible provider")

PROBLEM = {
    "problem": {
        "id": "ai_sum",
        "title": "边界两数之和",
        "description": "输入两个整数并输出和。",
        "input_description": "一行两个整数。",
        "output_description": "一个整数。",
        "samples": [{"input": "1 2\n", "output": "3\n"}],
        "constraints": "-10^9 <= a,b <= 10^9",
        "testcases": [
            {"input": "0 0\n", "output": "0\n"},
            {"input": "1000000000 -1000000000\n", "output": "0\n"},
        ],
        "hint": "注意负数。",
        "source": "AI",
        "tags": ["基础"],
        "time_limit": 1.0,
        "memory_limit": 128,
        "author": "AI Assistant",
        "difficulty": "入门",
    },
    "coverage": ["零值", "正负抵消", "整数边界"],
    "notes": "经过边界条件复核。",
}


@app.post("/v1/chat/completions")
async def chat_completions():
    import json

    return {
        "choices": [{"message": {"role": "assistant", "content": json.dumps(PROBLEM)}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
    }
