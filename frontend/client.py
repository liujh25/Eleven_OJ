from __future__ import annotations

import os
from typing import Any

import httpx


class APIError(RuntimeError):
    def __init__(self, status: int, message: str, data: Any = None):
        super().__init__(message)
        self.status = status
        self.data = data


class OJClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("OJ_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=30.0, follow_redirects=True)

    def request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self.client.request(method, path, **kwargs)
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise APIError(0, f"无法连接后端：{exc}") from exc
        if response.is_error or payload.get("code") != 200:
            raise APIError(response.status_code, payload.get("msg", "请求失败"), payload.get("data"))
        return payload.get("data")

    def get(self, path: str, **kwargs) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self.request("DELETE", path, **kwargs)

