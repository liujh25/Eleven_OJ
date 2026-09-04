from collections.abc import AsyncIterator

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


async def initialize_database() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
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

