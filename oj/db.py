from collections.abc import AsyncIterator

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oj.config import get_settings
from oj.models import Base, Language, User
from oj.security import hash_password

settings = get_settings()
engine = create_async_engine(settings.database_url, future=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


def _migrate_existing_database(connection: Connection) -> None:
    """Apply additive migrations required by databases created by earlier versions."""
    columns = {column["name"] for column in inspect(connection).get_columns("ai_tasks")}
    additions = {
        "task_type": "VARCHAR(32) NOT NULL DEFAULT 'authoring'",
        "parent_task_id": "VARCHAR(32)",
        "feedback": "TEXT",
        "test_plan": "JSON",
        "iteration_number": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.exec_driver_sql(f"ALTER TABLE ai_tasks ADD COLUMN {name} {definition}")
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_ai_tasks_parent_task_id ON ai_tasks (parent_task_id)"
    )
    # Normalize the spelling used by early development builds.
    connection.exec_driver_sql(
        "UPDATE access_audits SET action = 'view_logs' WHERE action = 'view_log'"
    )


async def initialize_database() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_migrate_existing_database)
    async with SessionFactory() as session:
        if await session.get(User, "admin") is None:
            session.add(
                User(
                    id="admin",
                    username="admin",
                    password_hash=hash_password("admintestpassword"),
                    role="admin",
                )
            )
        if await session.get(Language, "python") is None:
            session.add(
                Language(
                    name="python",
                    file_ext=".py",
                    compile_cmd=None,
                    run_cmd="python {src}",
                    time_limit=3.0,
                    memory_limit=128,
                )
            )
        if await session.get(Language, "cpp") is None:
            session.add(
                Language(
                    name="cpp",
                    file_ext=".cpp",
                    compile_cmd="g++ {src} -std=c++14 -O2 -o {exe}",
                    run_cmd="{exe}",
                    time_limit=3.0,
                    memory_limit=128,
                )
            )
        await session.commit()


async def close_database() -> None:
    await engine.dispose()
