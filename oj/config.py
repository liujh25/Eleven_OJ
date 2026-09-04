from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/oj.db"
    session_cookie: str = "oj_session"
    session_ttl_hours: int = 24
    cookie_secure: bool = False
    executor_enabled: bool = True
    ai_timeout_seconds: float = 90.0
    data_dir: Path = Path("data")

    model_config = SettingsConfigDict(env_prefix="OJ_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

