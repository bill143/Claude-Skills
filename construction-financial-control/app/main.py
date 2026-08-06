"""FastAPI application entrypoint.

Run: uvicorn app.main:app --reload
API docs: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    approvals,
    audit,
    auth,
    budgets,
    change_orders,
    dashboard,
    projects,
    purchase_orders,
    vendors,
)
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        # Dev convenience only — production schema is managed by Alembic.
        from app.db import base  # noqa: F401  (registers all models)
        from app.db.base_class import Base
        from app.db.session import engine

        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    projects.router,
    vendors.router,
    budgets.router,
    change_orders.router,
    purchase_orders.router,
    approvals.router,
    audit.router,
    dashboard.router,
):
    app.include_router(router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
