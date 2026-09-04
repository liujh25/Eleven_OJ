from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from oj.ai_tasks import cancel_all_ai_tasks
from oj.api import envelope
from oj.config import get_settings
from oj.db import get_db
from oj.dependencies import admin_user
from oj.judge_tasks import cancel_all
from oj.models import (
    AIConfig,
    AITask,
    AccessAudit,
    Language,
    LoginSession,
    Problem,
    Submission,
    TestCaseResult,
    User,
)
from oj.security import hash_password

router = APIRouter(prefix="/api", tags=["system"])


@router.post("/reset/")
async def reset_system(
    response: Response,
    _: User = Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    await cancel_all_ai_tasks()
    await cancel_all()
    for model in (
        TestCaseResult,
        AccessAudit,
        AITask,
        AIConfig,
        Submission,
        LoginSession,
        Problem,
        Language,
        User,
    ):
        await db.execute(delete(model))
    db.add(
        User(
            id="admin",
            username="admin",
            password_hash=hash_password("admintestpassword"),
            role="admin",
        )
    )
    db.add_all(
        [
            Language(
                name="python",
                file_ext=".py",
                compile_cmd=None,
                run_cmd="python {src}",
                time_limit=3.0,
                memory_limit=128,
            ),
            Language(
                name="cpp",
                file_ext=".cpp",
                compile_cmd="g++ {src} -std=c++14 -O2 -o {exe}",
                run_cmd="{exe}",
                time_limit=3.0,
                memory_limit=128,
            ),
        ]
    )
    await db.commit()
    response.delete_cookie(get_settings().session_cookie)
    return envelope(None, "system reset successfully")
