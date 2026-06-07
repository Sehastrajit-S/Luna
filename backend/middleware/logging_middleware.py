"""
Request ID + structured logging middleware.

Attaches a unique request_id to every request, adds it to response headers,
and configures Python's logging to include it in every log line.

Config (.env):
  log_level=INFO          # DEBUG | INFO | WARNING | ERROR
  log_format=text         # text | json  (json is machine-readable for log aggregation)
"""
import logging
import logging.config
import time
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings

# ── Context variable for request correlation ──────────────────────────────────
# Accessible from any async/sync code in the same request context.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique X-Request-ID into every request/response cycle.
    The ID is stored in a ContextVar so loggers can include it automatically.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use client-provided ID if present (e.g., from a reverse proxy), else generate.
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        request_id_var.set(rid)

        # Store on request.state for easy access in route handlers
        request.state.request_id = rid

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Attach to response for client correlation
        response.headers["X-Request-ID"] = rid

        # Log the request completion
        logger = logging.getLogger("luna.http")
        status = response.status_code
        method = request.method
        path = request.url.path

        # Skip noisy health checks from logs
        if path in ("/api/system/health",) and status == 200:
            return response

        log_level = logging.WARNING if status >= 400 else logging.INFO
        logger.log(
            log_level,
            "%s %s %d (%.1fms) [%s]",
            method, path, status, elapsed_ms, rid,
        )

        return response


# ── Logging configuration ─────────────────────────────────────────────────────

class RequestIDFilter(logging.Filter):
    """Injects request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


def configure_logging() -> None:
    """
    Configure structured logging for the entire backend.

    Call this once at application startup (before any loggers are used).
    Reads log_level and log_format from settings.
    """
    log_level = getattr(settings, "log_level", "INFO").upper()
    log_format = getattr(settings, "log_format", "text").lower()

    if log_format == "json":
        # JSON format for production log aggregation (ELK, CloudWatch, etc.)
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","request_id":"%(request_id)s","message":"%(message)s"}'
    else:
        # Human-readable format for development
        fmt = "%(asctime)s | %(levelname)-7s | %(name)-30s | [%(request_id)s] %(message)s"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIDFilter,
            },
        },
        "formatters": {
            "default": {
                "format": fmt,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
                "filters": ["request_id"],
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
        # Quiet down noisy libraries
        "loggers": {
            "uvicorn": {"level": "INFO"},
            "uvicorn.access": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "chromadb": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING" if not settings.db_echo else "INFO"},
        },
    })
