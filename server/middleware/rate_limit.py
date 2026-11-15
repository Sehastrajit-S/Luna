"""
Sliding-window rate limiter — no Redis required.

Uses an in-memory counter keyed by (client_ip | X-Luna-User) with a 60-second
window. Suitable for single-instance deployments. For horizontal scaling,
swap the _store dict for a shared Redis connection.

Config (.env):
  rate_limit_enabled=true
  rate_limit_per_minute=60    # max requests per window
  rate_limit_burst=20         # extra burst tokens above the per-minute quota
"""
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings

# paths that are never rate-limited
_SKIP_PATHS = {
    "/api/system/health",
    "/api/auth/check",
    "/api/channels/discord",   # Discord pings must always respond instantly
}


class _Window:
    """Sliding window of request timestamps for one identity."""
    __slots__ = ("timestamps",)

    def __init__(self):
        self.timestamps: Deque[float] = deque()

    def is_allowed(self, now: float, limit: int, burst: int, window: float = 60.0) -> bool:
        # Evict timestamps older than the window
        while self.timestamps and now - self.timestamps[0] > window:
            self.timestamps.popleft()
        if len(self.timestamps) < limit + burst:
            self.timestamps.append(now)
            return True
        return False


_store: dict[str, _Window] = defaultdict(_Window)


def _identity(request: Request) -> str:
    """Derive a stable identity string for rate-limit bucketing."""
    # Prefer an explicit user header (set by auth layer)
    user = request.headers.get("X-Luna-User")
    if user:
        return f"user:{user}"
    # Fall back to IP
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if path in _SKIP_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        identity = _identity(request)
        window = _store[identity]
        now = time.monotonic()

        if not window.is_allowed(now, settings.rate_limit_per_minute, settings.rate_limit_burst):
            return JSONResponse(
                {"detail": "Rate limit exceeded. Slow down and try again in a moment."},
                status_code=429,
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        remaining = max(
            0,
            settings.rate_limit_per_minute + settings.rate_limit_burst - len(window.timestamps),
        )
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
