"""SQLAlchemy engine + session factory + FastAPI dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # check_same_thread: share the dev/test DB across threads.
    # timeout: wait for SQLite's single writer lock instead of erroring, so
    # concurrency tests exercise the compare-and-swap guards deterministically.
    connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def locked_get(db: Session, model, pk: int):
    """Load a row under SELECT ... FOR UPDATE (row lock held until commit).

    SQLite has no row locks (its single-writer lock serializes transactions
    instead), so the FOR UPDATE clause is skipped there — status-guard checks
    inside the transaction remain the correctness backstop on both backends.
    """
    if db.get_bind().dialect.name == "sqlite":
        return db.get(model, pk)
    return db.get(model, pk, with_for_update=True)
