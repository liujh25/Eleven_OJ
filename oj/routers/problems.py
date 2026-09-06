from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import envelope, fail
from oj.db import get_db
from oj.dependencies import admin_user, current_user
from oj.models import AccessAudit, AITask, Problem, Submission, TestCaseResult, User
from oj.schemas import ProblemBody, VisibilityBody

router = APIRouter(prefix="/api/problems", tags=["problems"])


def problem_data(problem: Problem) -> dict:
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "input_description": problem.input_description,
        "output_description": problem.output_description,
        "samples": problem.samples,
        "constraints": problem.constraints,
        "testcases": problem.testcases,
        "hint": problem.hint or "",
        "source": problem.source or "",
        "tags": problem.tags or [],
        "time_limit": problem.time_limit or 3.0,
        "memory_limit": problem.memory_limit or 128,
        "author": problem.author or "",
        "difficulty": problem.difficulty or "",
    }


def apply_problem(problem: Problem, body: ProblemBody) -> None:
    values = body.model_dump()
    values["samples"] = [item.model_dump() for item in body.samples]
    values["testcases"] = [item.model_dump() for item in body.testcases]
    values["time_limit"] = body.time_limit or 0.0
    values["memory_limit"] = body.memory_limit or 0
    for key, value in values.items():
        setattr(problem, key, value)


@router.get("/")
async def list_problems(
    tag: str | None = Query(default=None, max_length=50),
    keyword: str | None = Query(default=None, max_length=100),
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    problems = (await db.scalars(select(Problem).order_by(Problem.id))).all()
    if tag is not None:
        normalized_tag = tag.strip().casefold()
        if not normalized_tag:
            fail(400, "tag must not be blank")
        problems = [
            item
            for item in problems
            if normalized_tag in {value.casefold() for value in (item.tags or [])}
        ]
    if keyword is not None:
        normalized_keyword = keyword.strip().casefold()
        if not normalized_keyword:
            fail(400, "keyword must not be blank")
        terms = normalized_keyword.split()
        problems = [
            item
            for item in problems
            if all(
                term
                in "\n".join(
                    [
                        item.id,
                        item.title,
                        item.description,
                        item.source or "",
                        item.author or "",
                        item.difficulty or "",
                        *(item.tags or []),
                    ]
                ).casefold()
                for term in terms
            )
        ]
    return envelope(
        [
            {
                "id": item.id,
                "title": item.title,
                "tags": item.tags or [],
                "difficulty": item.difficulty or "",
            }
            for item in problems
        ]
    )


@router.post("/")
async def add_problem(
    body: ProblemBody,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Problem, body.id) is not None:
        fail(409, "problem id already exists")
    problem = Problem(
        id=body.id,
        title=body.title,
        description="",
        input_description="",
        output_description="",
        samples=[],
        constraints="",
        testcases=[],
    )
    apply_problem(problem, body)
    db.add(problem)
    await db.commit()
    return envelope({"id": problem.id}, "add success")


@router.get("/{problem_id}")
async def get_problem(
    problem_id: str,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    problem = await db.get(Problem, problem_id)
    if problem is None:
        fail(404, "problem not found")
    return envelope(problem_data(problem))


@router.put("/{problem_id}")
async def update_problem(
    problem_id: str,
    body: ProblemBody,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.id != problem_id:
        fail(400, "body id must match path problem_id")
    problem = await db.get(Problem, problem_id)
    if problem is None:
        fail(404, "problem not found")
    apply_problem(problem, body)
    await db.commit()
    return envelope({"id": problem.id}, "update success")


@router.delete("/{problem_id}")
async def delete_problem(
    problem_id: str,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    problem = await db.get(Problem, problem_id)
    if problem is None:
        fail(404, "problem not found")
    submission_ids = select(Submission.id).where(Submission.problem_id == problem_id)
    # SQLite foreign-key enforcement can differ between deployments.  Delete
    # dependants explicitly so the API contract remains deterministic.
    await db.execute(delete(TestCaseResult).where(TestCaseResult.submission_id.in_(submission_ids)))
    await db.execute(delete(AccessAudit).where(AccessAudit.problem_id == problem_id))
    await db.execute(delete(Submission).where(Submission.problem_id == problem_id))
    await db.execute(delete(AITask).where(AITask.problem_id == problem_id))
    await db.delete(problem)
    await db.commit()
    return envelope({"id": problem_id}, "delete success")


@router.put("/{problem_id}/log_visibility")
async def update_log_visibility(
    problem_id: str,
    body: VisibilityBody,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    problem = await db.get(Problem, problem_id)
    if problem is None:
        fail(404, "problem not found")
    problem.public_cases = body.public_cases
    await db.commit()
    return envelope(
        {"problem_id": problem.id, "public_cases": problem.public_cases},
        "log visibility updated",
    )
