from __future__ import annotations

import asyncio

from sqlalchemy import delete

from oj.db import SessionFactory
from oj.evaluator import evaluate
from oj.models import Language, Problem, Submission, TestCaseResult

_tasks: set[asyncio.Task] = set()


async def run_submission(submission_id: str) -> None:
    async with SessionFactory() as db:
        submission = await db.get(Submission, submission_id)
        if submission is None:
            return
        problem = await db.get(Problem, submission.problem_id)
        language = await db.get(Language, submission.language)
        if problem is None or language is None:
            submission.status = "error"
            submission.error_info = "problem or language is no longer available"
            await db.commit()
            return
        try:
            result = await evaluate(problem, language, submission.code)
            await db.execute(
                delete(TestCaseResult).where(TestCaseResult.submission_id == submission.id)
            )
            for detail in result.pop("details"):
                db.add(
                    TestCaseResult(
                        submission_id=submission.id,
                        case_number=detail["id"],
                        result=detail["result"],
                        time=detail["time"],
                        memory=detail["memory"],
                    )
                )
            for key, value in result.items():
                setattr(submission, key, value)
        except asyncio.CancelledError:
            submission.status = "error"
            submission.error_info = "evaluation cancelled"
            await db.commit()
            raise
        except Exception:
            submission.status = "error"
            submission.error_info = "judge internal error"
        await db.commit()


def schedule_submission(submission_id: str) -> None:
    task = asyncio.create_task(run_submission(submission_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def cancel_all() -> None:
    for task in list(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
