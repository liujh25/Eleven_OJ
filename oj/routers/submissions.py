from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import envelope, fail, page_slice
from oj.config import get_settings
from oj.db import get_db
from oj.dependencies import admin_user, current_user
from oj.judge_tasks import schedule_submission
from oj.models import Language, Problem, Submission, User, utcnow
from oj.schemas import SubmissionBody

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def submission_data(item: Submission) -> dict:
    base = {"submission_id": item.id, "status": item.status}
    if item.status == "pending":
        return base
    return {
        **base,
        "score": item.score,
        "counts": item.counts,
        "compile_info": item.compile_info,
        "run_info": item.run_info,
        "error_info": item.error_info or "",
    }


@router.post("/")
async def submit(
    body: SubmissionBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    problem = await db.get(Problem, body.problem_id)
    language = await db.get(Language, body.language)
    if problem is None or language is None:
        fail(404, "problem or language not found")
    recent = await db.scalar(
        select(func.count(Submission.id)).where(
            Submission.user_id == user.id,
            Submission.created_at >= utcnow() - timedelta(minutes=1),
        )
    )
    if (recent or 0) >= 3:
        fail(429, "submission rate limit exceeded")
    item = Submission(
        user_id=user.id,
        problem_id=body.problem_id,
        language=body.language,
        code=body.code,
        status="pending",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    if get_settings().executor_enabled:
        schedule_submission(item.id)
    return envelope({"submission_id": item.id, "status": "pending"})


@router.get("/")
async def list_submissions(
    user_id: str | None = None,
    problem_id: str | None = None,
    status: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id is None and problem_id is None:
        fail(400, "user_id or problem_id is required")
    if status is not None and status not in {"pending", "success", "error"}:
        fail(400, "invalid submission status")
    offset, limit = page_slice(page, page_size)
    query = select(Submission)
    if user_id is not None:
        if user.role != "admin" and user_id != user.id:
            fail(403, "permission denied")
        query = query.where(Submission.user_id == user_id)
    elif user.role != "admin":
        query = query.where(Submission.user_id == user.id)
    if problem_id is not None:
        query = query.where(Submission.problem_id == problem_id)
    if status is not None:
        query = query.where(Submission.status == status)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(Submission.created_at.desc(), Submission.id.desc())
    if limit is not None:
        query = query.offset(offset or 0).limit(limit)
    items = list((await db.scalars(query)).all())
    summaries = []
    for item in items:
        value: dict[str, Any] = {"submission_id": item.id, "status": item.status}
        if item.status == "success":
            value.update({"score": item.score, "counts": item.counts})
        summaries.append(value)
    return envelope({"total": total, "submissions": summaries})


@router.get("/{submission_id}")
async def get_submission(
    submission_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Submission, submission_id)
    if item is None:
        fail(404, "submission not found")
    if user.role != "admin" and item.user_id != user.id:
        fail(403, "permission denied")
    return envelope(submission_data(item))


@router.put("/{submission_id}/rejudge")
async def rejudge(
    submission_id: str,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Submission, submission_id)
    if item is None:
        fail(404, "submission not found")
    item.status = "pending"
    item.score = None
    item.counts = None
    item.compile_info = None
    item.run_info = None
    item.error_info = None
    await db.commit()
    if get_settings().executor_enabled:
        schedule_submission(item.id)
    return envelope({"submission_id": item.id, "status": "pending"}, "rejudge started")
