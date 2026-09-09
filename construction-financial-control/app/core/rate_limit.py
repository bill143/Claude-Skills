"""Sliding-window in-memory rate limiter.

Scope: per-process abuse protection for auth and mutating endpoints. This is
deliberately dependency-free and correct for a single API instance; when the
API scales horizontally, front it with a shared limiter (e.g. Redis-backed
slowapi or an API gateway) — tracked in PRODUCTION_READINESS.md.
"""
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

_WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            while window and now - window[0] > _WINDOW_SECONDS:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True


limiter = RateLimiter()


def _limit_for(request: Request) -> int:
    path = request.url.path
    if path.endswith("/auth/login"):
        return settings.RATE_LIMIT_AUTH_PER_MINUTE
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        return settings.RATE_LIMIT_MUTATING_PER_MINUTE
    return settings.RATE_LIMIT_DEFAULT_PER_MINUTE


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        limit = _limit_for(request)
        bucket = "auth" if request.url.path.endswith("/auth/login") else (
            "mutate" if request.method in ("POST", "PUT", "PATCH", "DELETE") else "read"
        )
        if not limiter.allow(f"{client}:{bucket}", limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded, retry later"},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
