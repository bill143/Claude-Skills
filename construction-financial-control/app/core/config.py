"""Application configuration with environment-specific hardening.

ENVIRONMENT selects the profile (dev / stage / prod). Production refuses to
start with insecure defaults: default/short SECRET_KEY, wildcard CORS, DEBUG,
or runtime table creation. See .env.example for the full variable list.
"""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_KEY = "change-me-in-production-please-this-is-a-dev-only-default"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Construction Financial Control System"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["dev", "stage", "prod"] = "dev"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = INSECURE_DEFAULT_KEY
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    # Comma-separated list of allowed browser origins (no wildcard in prod).
    CORS_ORIGINS: str = "http://localhost:8501"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://cfcs:cfcs@localhost:5432/cfcs"

    # Redis / Celery (optional — only needed if you run the worker)
    REDIS_URL: str = "redis://localhost:6379/0"
    # Include Redis in the /health/ready check (enable when the worker is deployed).
    READINESS_CHECK_REDIS: bool = False

    # Budget control tolerance: a PO may exceed remaining budget by this
    # fraction before the project's budget_control action (STOP/WARN) fires.
    BUDGET_TOLERANCE_PCT: float = 0.0

    # Dev convenience: create tables on startup. Ignored (forced off) outside
    # dev — stage/prod schema is managed exclusively by Alembic migrations.
    AUTO_CREATE_TABLES: bool = False

    # Observability
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # Rate limiting (in-memory, per instance; front with a shared limiter when
    # scaling horizontally — see docs/runbooks/deployment.md).
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_MUTATING_PER_MINUTE: int = 120
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 300

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return ",".join(o.strip() for o in v.split(",") if o.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o for o in self.CORS_ORIGINS.split(",") if o]

    @model_validator(mode="after")
    def _enforce_environment_safety(self) -> "Settings":
        if self.ENVIRONMENT in ("stage", "prod"):
            object.__setattr__(self, "AUTO_CREATE_TABLES", False)
        if self.ENVIRONMENT == "prod":
            problems = []
            if self.SECRET_KEY == INSECURE_DEFAULT_KEY or len(self.SECRET_KEY) < 32:
                problems.append("SECRET_KEY must be set to a random value of >= 32 chars")
            if self.DEBUG:
                problems.append("DEBUG must be false")
            if "*" in self.cors_origin_list or not self.cors_origin_list:
                problems.append("CORS_ORIGINS must be an explicit origin list (no '*')")
            if self.DATABASE_URL.startswith("sqlite"):
                problems.append("SQLite is not supported in prod; use PostgreSQL")
            if problems:
                raise ValueError("Refusing to start in prod: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
