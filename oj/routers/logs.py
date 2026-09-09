from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import envelope, fail, page_slice
from oj.db import get_db
from oj.dependencies import admin_user, current_user
from oj.models import AccessAudit, Problem, Submission, TestCaseResult, User

router = APIRouter(prefix="/api", tags=["logs"])


@router.get("/submissions/{submission_id}/log")
async def submission_log(
    submission_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await db.get(Submission, submission_id)
    if submission is None:
        fail(404, "submission not found")
    problem = await db.get(Problem, submission.problem_id)
    if problem is None:
        fail(404, "problem not found")
    is_admin = user.role == "admin"
    is_owner = submission.user_id == user.id
    allowed = is_admin or is_owner or problem.public_cases
    db.add(
        AccessAudit(
            user_id=user.id,
            problem_id=problem.id,
            submission_id=submission.id,
            action="view_logs",
            status="200" if allowed else "403",
        )
    )
    await db.commit()
    if not allowed:
        fail(403, "permission denied")
    details = []
    if is_admin or problem.public_cases:
        results = (
            await db.scalars(
                select(TestCaseResult)
                .where(TestCaseResult.submission_id == submission.id)
                .order_by(TestCaseResult.case_number)
            )
        ).all()
        details = [
            {
                "id": item.case_number,
                "result": item.result,
                "time": item.time,
                "memory": item.memory,
            }
            for item in results
        ]
    return envelope({"details": details, "score": submission.score, "counts": submission.counts})


@router.get("/logs/access/")
async def access_logs(
    user_id: str | None = None,
    problem_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    offset, limit = page_slice(page, page_size)
    query = select(AccessAudit)
    if user_id is not None:
        query = query.where(AccessAudit.user_id == user_id)
    if problem_id is not None:
        query = query.where(AccessAudit.problem_id == problem_id)
    query = query.order_by(AccessAudit.time.desc(), AccessAudit.id.desc())
    if limit is not None:
        query = query.offset(offset or 0).limit(limit)
    rows = list((await db.scalars(query)).all())
    return envelope(
        [
            {
                "user_id": row.user_id,
                "problem_id": row.problem_id,
                "action": row.action,
                "time": row.time.isoformat(),
                "status": row.status,
            }
            for row in rows
        ]
    )
