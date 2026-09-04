from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.ai_tasks import cancel_ai_task, schedule_ai_task
from oj.api import envelope, fail
from oj.crypto import encrypt_secret
from oj.db import get_db
from oj.dependencies import current_user
from oj.models import AIConfig, AITask, Problem, User
from oj.schemas import AIConfigBody, AITaskBody

router = APIRouter(prefix="/api/ai", tags=["ai-authoring"])


def task_data(task: AITask) -> dict:
    return {
        "task_id": task.id,
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
    task = AITask(user_id=user.id, requirement=body.requirement, problem_id=body.problem_id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    schedule_ai_task(task.id)
    return envelope({"task_id": task.id, "status": "pending"}, "task created")


@router.get("/problem-tasks/")
async def list_tasks(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
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
