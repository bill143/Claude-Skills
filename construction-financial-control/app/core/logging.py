"""Structured JSON logging with request-ID correlation.

Every request gets an X-Request-ID (accepted from the caller or generated),
stored in a contextvar so any log line emitted while handling that request —
including from services — carries the same correlation ID. Unhandled errors
return the ID to the client so users can quote it in incident reports.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

access_logger = logging.getLogger("cfcs.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        for key in ("method", "path", "status_code", "duration_ms", "client", "user"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s", defaults={"request_id": "-"}
        ))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # uvicorn's own access log duplicates ours; keep error channel only.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign/propagate X-Request-ID and emit one structured access line per request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception(
                "unhandled error",
                extra={"method": request.method, "path": request.url.path,
                       "client": request.client.host if request.client else None},
            )
            raise
        finally:
            request_id_ctx.reset(token)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        request_id_ctx.set(request_id)
        access_logger.info(
            "request",
            extra={"method": request.method, "path": request.url.path,
                   "status_code": response.status_code, "duration_ms": duration_ms,
                   "client": request.client.host if request.client else None},
        )
        response.headers["X-Request-ID"] = request_id
        return response
