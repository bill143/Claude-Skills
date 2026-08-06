"""Application configuration.

Settings are loaded from environment variables (optionally via a .env file).
See .env.example at the project root for the full list.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Construction Financial Control System"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-me-in-production-please-this-is-a-dev-only-default"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://cfcs:cfcs@localhost:5432/cfcs"

    # Redis / Celery (optional — only needed if you run the worker)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Budget control tolerance: a PO may exceed remaining budget by this
    # fraction before the project's budget_control action (STOP/WARN) fires.
    BUDGET_TOLERANCE_PCT: float = 0.0

    # Dev convenience: create tables on startup (use Alembic in production)
    AUTO_CREATE_TABLES: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
