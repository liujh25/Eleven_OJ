from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import envelope, fail, page_slice
from oj.config import get_settings
from oj.db import get_db
from oj.dependencies import admin_user, current_user
from oj.models import LoginSession, Submission, User
from oj.schemas import Credentials, RoleUpdate
from oj.security import (
    hash_password,
    new_session_token,
    session_expiry,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["users"])


async def user_data(db: AsyncSession, user: User) -> dict:
    submit_count = await db.scalar(
        select(func.count(Submission.id)).where(Submission.user_id == user.id)
    )
    resolved = await db.scalar(
        select(func.count(func.distinct(Submission.problem_id))).where(
            Submission.user_id == user.id, Submission.status == "success", Submission.score > 0
        )
    )
    return {
        "user_id": user.id,
        "username": user.username,
        "join_time": user.join_time.date().isoformat(),
        "role": user.role,
        "submit_count": submit_count or 0,
        "resolve_count": resolved or 0,
    }


@router.post("/auth/login")
async def login(body: Credentials, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        fail(401, "invalid username or password")
    if user.role == "banned":
        fail(403, "user is banned")
    raw_token = new_session_token()
    settings = get_settings()
    db.add(
        LoginSession(
            token_hash=token_hash(raw_token),
            user_id=user.id,
            expires_at=session_expiry(settings.session_ttl_hours),
        )
    )
    await db.commit()
    response.set_cookie(
        settings.session_cookie,
        raw_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
    )
    return envelope(
        {"user_id": user.id, "username": user.username, "role": user.role}, "login success"
    )


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie)
    if raw_token:
        await db.execute(
            delete(LoginSession).where(LoginSession.token_hash == token_hash(raw_token))
        )
        await db.commit()
    response.delete_cookie(settings.session_cookie)
    return envelope(None, "logout success")


async def create_user(body: Credentials, role: str, db: AsyncSession) -> User:
    if await db.scalar(select(User.id).where(User.username == body.username)):
        fail(400, "username already exists")
    user = User(username=body.username, password_hash=hash_password(body.password), role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/")
async def register(body: Credentials, db: AsyncSession = Depends(get_db)):
    user = await create_user(body, "user", db)
    return envelope(await user_data(db, user), "register success")


@router.post("/users/admin")
async def create_admin(
    body: Credentials,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await create_user(body, "admin", db)
    return envelope({"user_id": user.id, "username": user.username})


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    actor: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if actor.id != user_id and actor.role != "admin":
        fail(403, "permission denied")
    user = await db.get(User, user_id)
    if user is None:
        fail(404, "user not found")
    return envelope(await user_data(db, user))


@router.put("/users/{user_id}/role")
async def update_role(
    user_id: str,
    body: RoleUpdate,
    actor: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        fail(404, "user not found")
    if user.id == actor.id and body.role != "admin":
        fail(409, "administrator cannot demote the active account")
    user.role = body.role
    if body.role == "banned":
        await db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    await db.commit()
    return envelope({"user_id": user.id, "role": user.role}, "role updated")


@router.get("/users/")
async def list_users(
    page: int | None = None,
    page_size: int | None = None,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    offset, limit = page_slice(page, page_size)
    total = await db.scalar(select(func.count(User.id))) or 0
    query = select(User).order_by(User.join_time, User.id)
    if limit is not None:
        query = query.offset(offset or 0).limit(limit)
    users = list((await db.scalars(query)).all())
    return envelope({"total": total, "users": [await user_data(db, user) for user in users]})
