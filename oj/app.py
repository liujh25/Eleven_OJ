from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from oj.ai_tasks import cancel_all_ai_tasks
from oj.api import envelope
from oj.db import close_database, initialize_database
from oj.judge_tasks import cancel_all
from oj.routers import ai, languages, logs, problems, submissions, system, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield
    await cancel_all_ai_tasks()
    await cancel_all()
    await close_database()


app = FastAPI(title="Async OJ", version="1.5.0", lifespan=lifespan)
app.include_router(users.router)
app.include_router(problems.router)
app.include_router(languages.router)
app.include_router(submissions.router)
app.include_router(logs.router)
app.include_router(system.router)
app.include_router(ai.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code, content=envelope(None, str(exc.detail), exc.status_code)
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content=envelope({"errors": errors}, "request validation failed", 400),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    return JSONResponse(status_code=500, content=envelope(None, "internal server error", 500))


@app.get("/health")
async def health():
    return envelope({"status": "ok"})
