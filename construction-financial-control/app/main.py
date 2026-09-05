"""FastAPI application entrypoint.

Run: uvicorn app.main:app --reload
API docs: http://localhost:8000/docs (dev only)

Schema management: Alembic (`alembic upgrade head`). Runtime create_all is a
dev-only convenience gated on ENVIRONMENT=dev + AUTO_CREATE_TABLES=true.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import (
    approvals,
    audit,
    auth,
    budgets,
    change_orders,
    cost_codes,
    dashboard,
    projects,
    purchase_orders,
    vendors,
)
from app.core.config import settings
from app.core.logging import RequestContextMiddleware, configure_logging, request_id_ctx
from app.core.rate_limit import RateLimitMiddleware

logger = logging.getLogger("cfcs.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
    if settings.ENVIRONMENT == "dev" and settings.AUTO_CREATE_TABLES:
        # Dev convenience only — stage/prod schema is managed by Alembic and
        # config.py forces this flag off outside dev.
        from app.db import base  # noqa: F401  (registers all models)
        from app.db.base_class import Base
        from app.db.session import engine

        Base.metadata.create_all(bind=engine)
        logger.warning("AUTO_CREATE_TABLES ran (dev only) — use Alembic everywhere else")
        from app.db.session import SessionLocal
        from app.services.wbs_service import seed_cost_codes

        with SessionLocal() as db:
            loaded = seed_cost_codes(db)
            if loaded:
                logger.info("seeded CSI MasterFormat cost-code library (%d codes)", loaded)
    logger.info("startup complete", extra={"path": settings.ENVIRONMENT})
    yield


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "prod" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "prod" else None,
)

# Middleware order (outermost first): request-ID/access-log -> rate limit -> CORS.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    correlation_id = request_id_ctx.get()
    logger.exception("unhandled exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "correlation_id": correlation_id},
        headers={"X-Request-ID": correlation_id},
    )


for router in (
    auth.router,
    projects.router,
    vendors.router,
    cost_codes.router,
    budgets.router,
    change_orders.router,
    purchase_orders.router,
    approvals.router,
    audit.router,
    dashboard.router,
):
    app.include_router(router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
@app.get("/health/live")
def liveness():
    """Process is up. No dependency checks — safe for container liveness probes."""
    return {"status": "alive", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/health/ready")
def readiness():
    """Dependency checks: DB (always) and Redis (when READINESS_CHECK_REDIS)."""
    from app.db.session import engine

    checks: dict[str, str] = {}
    healthy = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
        healthy = False

    if settings.READINESS_CHECK_REDIS:
        try:
            import redis as redis_lib

            redis_lib.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {type(exc).__name__}"
            healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(status_code=status_code,
                        content={"status": "ready" if healthy else "degraded", "checks": checks})
