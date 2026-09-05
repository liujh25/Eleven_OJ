from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="user", index=True)
    join_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user: Mapped[User] = relationship()


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    input_description: Mapped[str] = mapped_column(Text)
    output_description: Mapped[str] = mapped_column(Text)
    samples: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    constraints: Mapped[str] = mapped_column(Text)
    testcases: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    hint: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(200), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    time_limit: Mapped[float] = mapped_column(Float, default=3.0)
    memory_limit: Mapped[int] = mapped_column(Integer, default=128)
    author: Mapped[str] = mapped_column(String(100), default="")
    difficulty: Mapped[str] = mapped_column(String(40), default="")
    public_cases: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Language(Base):
    __tablename__ = "languages"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    file_ext: Mapped[str] = mapped_column(String(16))
    compile_cmd: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_cmd: Mapped[str] = mapped_column(Text)
    time_limit: Mapped[float] = mapped_column(Float, default=3.0)
    memory_limit: Mapped[int] = mapped_column(Integer, default=128)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(ForeignKey("languages.name"), index=True)
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    counts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compile_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class TestCaseResult(Base):
    __test__ = False
    __tablename__ = "testcase_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), index=True
    )
    case_number: Mapped[int] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(8))
    time: Mapped[float] = mapped_column(Float, default=0.0)
    memory: Mapped[float] = mapped_column(Float, default=0.0)


class AccessAudit(Base):
    __tablename__ = "access_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    submission_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(32), default="view_logs")
    status: Mapped[str] = mapped_column(String(3))
    time: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AIConfig(Base):
    __tablename__ = "ai_configs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    provider_url: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    input_price: Mapped[float] = mapped_column(Float, default=0.0)
    output_price: Mapped[float] = mapped_column(Float, default=0.0)
    price_unit: Mapped[int] = mapped_column(Integer, default=1_000_000)


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    requirement: Mapped[str] = mapped_column(Text)
    problem_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    task_type: Mapped[str] = mapped_column(String(32), default="authoring")
    parent_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    iteration_number: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    progress: Mapped[str] = mapped_column(String(200), default="等待执行")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
