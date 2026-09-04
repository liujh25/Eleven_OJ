from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oj.api import envelope, fail
from oj.db import get_db
from oj.dependencies import current_user
from oj.evaluator import validate_language_commands
from oj.models import Language, User
from oj.schemas import LanguageBody

router = APIRouter(prefix="/api/languages", tags=["languages"])


@router.get("/")
async def list_languages(db: AsyncSession = Depends(get_db)):
    names = list((await db.scalars(select(Language.name).order_by(Language.name))).all())
    return envelope({"name": names})


@router.post("/")
async def register_language(
    body: LanguageBody,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Language, body.name) is not None:
        fail(409, "language already exists")
    try:
        validate_language_commands(body.compile_cmd, body.run_cmd)
    except ValueError as exc:
        fail(400, str(exc))
    language = Language(**body.model_dump())
    db.add(language)
    await db.commit()
    return envelope({"name": language.name}, "language registered")
