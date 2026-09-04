from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException


def envelope(data: Any = None, msg: str = "success", code: int = 200) -> dict[str, Any]:
    return {"code": code, "msg": msg, "data": data}


def fail(code: int, msg: str) -> NoReturn:
    raise HTTPException(status_code=code, detail=msg)


def page_slice(page: int | None, page_size: int | None) -> tuple[int | None, int | None]:
    if page is not None and page_size is None:
        fail(400, "page_size is required when page is provided")
    if page is not None and page < 1:
        fail(400, "page must be positive")
    if page_size is not None and not 1 <= page_size <= 200:
        fail(400, "page_size must be between 1 and 200")
    if page_size is None:
        return None, None
    effective_page = page or 1
    return (effective_page - 1) * page_size, page_size
