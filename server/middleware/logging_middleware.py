"""
Request ID middleware.

Attaches a unique request_id to every request, adds it to response headers,
and logs request completion. Logging setup itself (handlers, formatters,
file rotation) lives in server.core.logging — configure_logging() is
re-exported here for backward compatibility.
"""
import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from server.core.logging import configure_logging, request_id_var  # noqa: F401

__all__ = ["RequestIDMiddleware", "configure_logging", "request_id_var"]


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
