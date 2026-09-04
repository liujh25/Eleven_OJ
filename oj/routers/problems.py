from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import envelope, fail
from oj.db import get_db
from oj.dependencies import admin_user, current_user
from oj.models import Problem, User
from oj.schemas import ProblemBody

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
        "time_limit": problem.time_limit,
        "memory_limit": problem.memory_limit,
        "author": problem.author or "",
        "difficulty": problem.difficulty or "",
    }


def apply_problem(problem: Problem, body: ProblemBody) -> None:
    values = body.model_dump()
    values["samples"] = [item.model_dump() for item in body.samples]
    values["testcases"] = [item.model_dump() for item in body.testcases]
    for key, value in values.items():
        setattr(problem, key, value)


@router.get("/")
async def list_problems(
    _: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    problems = (await db.scalars(select(Problem).order_by(Problem.id))).all()
    return envelope([{"id": item.id, "title": item.title} for item in problems])


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
    await db.delete(problem)
    await db.commit()
    return envelope({"id": problem_id}, "delete success")
