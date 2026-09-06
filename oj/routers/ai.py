from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.ai_tasks import cancel_ai_task, schedule_ai_task
from oj.api import envelope, fail
from oj.crypto import encrypt_secret
from oj.db import get_db
from oj.dependencies import current_user
from oj.luogu import LuoguFetchError, LuoguProblemNotFound, fetch_luogu_problem
from oj.models import AIConfig, AITask, Problem, User
from oj.schemas import (
    AIConfigBody,
    AIIterationBody,
    AITaskBody,
    AITestRefinementBody,
    LuoguTaskBody,
)

router = APIRouter(prefix="/api/ai", tags=["ai-authoring"])


def task_data(task: AITask) -> dict:
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "parent_task_id": task.parent_task_id,
        "iteration_number": task.iteration_number,
        "requirement": task.requirement,
        "feedback": task.feedback,
        "test_plan": task.test_plan,
        "external_source": (
            {
                key: task.external_source.get(key)
                for key in ("provider", "problem_id", "url", "title", "difficulty", "mode")
            }
            if task.external_source
            else None
        ),
        "status": task.status,
        "progress": task.progress,
        "result": task.result,
        "usage": {
            "input_tokens": task.input_tokens,
            "output_tokens": task.output_tokens,
            "total_tokens": task.input_tokens + task.output_tokens,
            "cost": task.cost,
            "currency": "USD",
        },
        "error": task.error,
    }


def check_owner(task: AITask, user: User) -> None:
    if task.user_id != user.id and user.role != "admin":
        fail(403, "permission denied")


async def completed_source(task_id: str, user: User, db: AsyncSession) -> AITask:
    task = await db.get(AITask, task_id)
    if task is None:
        fail(404, "source task not found")
    check_owner(task, user)
    if task.status != "completed" or not task.result:
        fail(409, "source task must be completed")
    return task


async def create_child_task(
    source: AITask,
    user: User,
    db: AsyncSession,
    *,
    task_type: str,
    feedback: str | None,
    test_plan: dict | None,
) -> AITask:
    if await db.get(AIConfig, user.id) is None:
        fail(400, "model configuration is required")
    task = AITask(
        user_id=user.id,
        requirement=source.requirement,
        problem_id=source.problem_id,
        task_type=task_type,
        parent_task_id=source.id,
        feedback=feedback,
        test_plan=test_plan,
        external_source=source.external_source,
        iteration_number=source.iteration_number + 1,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    schedule_ai_task(task.id)
    return task


@router.put("/model-config")
async def set_model_config(
    body: AIConfigBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    config = await db.get(AIConfig, user.id)
    values = body.model_dump(exclude={"api_key"})
    if config is None:
        config = AIConfig(
            user_id=user.id,
            encrypted_api_key=encrypt_secret(body.api_key),
            **values,
        )
        db.add(config)
    else:
        for key, value in values.items():
            setattr(config, key, value)
        config.encrypted_api_key = encrypt_secret(body.api_key)
    await db.commit()
    return envelope(
        {
            "provider_url": config.provider_url,
            "model": config.model,
            "api_key_configured": True,
            "input_price": config.input_price,
            "output_price": config.output_price,
            "price_unit": config.price_unit,
        },
        "model config updated",
    )


@router.post("/problem-tasks/")
async def create_task(
    body: AITaskBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(AIConfig, user.id) is None:
        fail(400, "model configuration is required")
    if body.problem_id and await db.get(Problem, body.problem_id) is None:
        fail(404, "problem not found")
    task = AITask(
        user_id=user.id,
        requirement=body.requirement,
        problem_id=body.problem_id,
        test_plan=body.test_plan.model_dump(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    schedule_ai_task(task.id)
    return envelope({"task_id": task.id, "status": "pending"}, "task created")


@router.post("/luogu-problem-tasks/")
async def create_luogu_task(
    body: LuoguTaskBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(AIConfig, user.id) is None:
        fail(400, "model configuration is required")
    try:
        reference = await fetch_luogu_problem(body.problem_id)
    except LuoguProblemNotFound as exc:
        fail(404, str(exc))
    except LuoguFetchError as exc:
        fail(502, str(exc))
    reference["mode"] = body.mode
    mode_name = "相似题" if body.mode == "similar" else "扩展题"
    requirement = f"基于洛谷 {body.problem_id} 的考点设计一道原创{mode_name}。"
    if body.additional_requirement:
        requirement += f" 附加要求：{body.additional_requirement}"
    task = AITask(
        user_id=user.id,
        requirement=requirement,
        task_type=f"luogu_{body.mode}",
        feedback=body.additional_requirement or None,
        test_plan=body.test_plan.model_dump(),
        external_source=reference,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    schedule_ai_task(task.id)
    return envelope(
        {
            "task_id": task.id,
            "status": task.status,
            "reference": {
                "problem_id": reference["problem_id"],
                "title": reference["title"],
                "difficulty": reference["difficulty"],
                "url": reference["url"],
                "mode": body.mode,
            },
        },
        "Luogu reference task created",
    )


@router.post("/problem-tasks/{task_id}/iterations")
async def iterate_task(
    task_id: str,
    body: AIIterationBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await completed_source(task_id, user, db)
    task = await create_child_task(
        source,
        user,
        db,
        task_type="iteration",
        feedback=body.feedback,
        test_plan=body.test_plan.model_dump() if body.test_plan else source.test_plan,
    )
    return envelope(
        {"task_id": task.id, "status": task.status, "parent_task_id": source.id},
        "iteration task created",
    )


@router.post("/problem-tasks/{task_id}/test-refinements")
async def refine_testcases(
    task_id: str,
    body: AITestRefinementBody,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await completed_source(task_id, user, db)
    task = await create_child_task(
        source,
        user,
        db,
        task_type="test_refinement",
        feedback="依据精细化测试策略补强测试点，同时保持题意和输入输出协议稳定。",
        test_plan=body.test_plan.model_dump(),
    )
    return envelope(
        {"task_id": task.id, "status": task.status, "parent_task_id": source.id},
        "test refinement task created",
    )


@router.get("/problem-tasks/")
async def list_tasks(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    query = select(AITask).order_by(AITask.created_at.desc())
    if user.role != "admin":
        query = query.where(AITask.user_id == user.id)
    tasks = list((await db.scalars(query.limit(100))).all())
    return envelope([task_data(task) for task in tasks])


@router.get("/problem-tasks/{task_id}")
async def get_task(
    task_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(AITask, task_id)
    if task is None:
        fail(404, "task not found")
    check_owner(task, user)
    return envelope(task_data(task))


@router.put("/problem-tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(AITask, task_id)
    if task is None:
        fail(404, "task not found")
    check_owner(task, user)
    if task.status in {"completed", "cancelled", "failed"}:
        fail(409, "task already ended")
    if not cancel_ai_task(task_id):
        task.status = "cancelled"
        task.progress = "任务已中断"
        await db.commit()
    return envelope({"task_id": task.id, "status": "cancelled"}, "task cancelled")
