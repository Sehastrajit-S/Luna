"""Who may use this Luna over Tailscale without the access token.

`tailscale serve` tells the server which tailnet user sent each request
(Tailscale-User-Login) and strips that header if a client tries to send it, so
requests from the server owner's own devices can be trusted without a token.
The owner is the user this machine is signed in to Tailscale as; more logins
can be added with `tailscale_trusted_logins`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import time

from server.config import settings

logger = logging.getLogger("luna.tailscale")

_CACHE_TTL_S = 300
_cache: tuple[float, frozenset[str]] | None = None
_lock = asyncio.Lock()


def _status() -> dict:
    binary = shutil.which("tailscale")
    if not binary:
        return {}
    try:
        out = subprocess.run([binary, "status", "--json"], capture_output=True, text=True, timeout=5, check=True).stdout
        return json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        logger.warning("Could not read Tailscale status: %s", e)
        return {}


def _owner_login(status: dict | None = None) -> str:
    """This machine's Tailscale login, or '' when Tailscale isn't available."""
    status = _status() if status is None else status
    user_id = status.get("Self", {}).get("UserID")
    return str(status.get("User", {}).get(str(user_id), {}).get("LoginName", "")).strip().lower()


def _load() -> frozenset[str]:
    logins = {x.strip().lower() for x in settings.tailscale_trusted_logins.split(",") if x.strip()}
    if settings.tailscale_trust_owner:
        owner = _owner_login()
        if owner:
            logins.add(owner)
    return frozenset(logins)


async def trusted_logins() -> frozenset[str]:
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[0] < _CACHE_TTL_S:
        return _cache[1]
    async with _lock:
        if _cache and now - _cache[0] < _CACHE_TTL_S:
            return _cache[1]
        logins = await asyncio.to_thread(_load)
        _cache = (time.monotonic(), logins)
        return logins


def reset_cache() -> None:
    global _cache
    _cache = None
