from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import fail
from oj.config import get_settings
from oj.db import get_db
from oj.models import LoginSession, User, utcnow
from oj.security import token_hash


async def current_user(
    request: Request, session: AsyncSession = Depends(get_db)
) -> User:
    raw_token = request.cookies.get(get_settings().session_cookie)
    if not raw_token:
        fail(401, "not logged in")
    login = await session.get(LoginSession, token_hash(raw_token))
    if login is None or login.expires_at <= utcnow():
        if login is not None:
            await session.delete(login)
            await session.commit()
        fail(401, "session expired")
    user = await session.get(User, login.user_id)
    if user is None:
        fail(401, "invalid session")
    if user.role == "banned":
        fail(403, "user is banned")
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        fail(403, "administrator required")
    return user

