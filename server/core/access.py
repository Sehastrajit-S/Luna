"""Access control for requests that reach Luna from another device.

Luna listens on 127.0.0.1 by default, and apps on the same machine (desktop app,
CLI, VS Code, Office) call it without credentials. Remote access goes through a
reverse proxy such as `tailscale serve`, which forwards from 127.0.0.1 too, so
the client address alone can't tell local from remote. Proxies do announce
themselves: `tailscale serve` always sets X-Forwarded-Host and strips any
Tailscale-* headers a client sends. A request is treated as remote when:

- it carries a forwarding header (X-Forwarded-*, Forwarded, X-Real-IP) or a
  Tailscale-* header, or
- it comes from a non-loopback address and `require_token_on_lan` is on
  (off by default so LAN mode and Docker port mapping keep working).

A remote request to /api is let in when either:

- it comes through `tailscale serve` from one of the server owner's devices:
  Tailscale sets Tailscale-User-Login (and strips client copies), the TCP peer
  is tailscaled on this machine (loopback), it isn't Funnel traffic, and the
  login is trusted (see server/services/tailscale_identity.py); or
- it presents Luna's access token (data/local_api_token) in the X-Luna-Token
  header, or as `luna_token` in the query string for clients that can't set
  headers (EventSource, WebSocket).
"""
from __future__ import annotations

import json
import logging
from ipaddress import ip_address
from urllib.parse import parse_qs

from server.services.settings_store import token_ok
from server.services.tailscale_identity import own_tailscale_ips, trusted_logins

logger = logging.getLogger("luna.access")

TOKEN_HEADER = b"x-luna-token"
TOKEN_QUERY = "luna_token"
_PROXY_HEADERS = {b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto", b"forwarded", b"x-real-ip"}

# Endpoints that must work without Luna's token: liveness checks, CORS-free
# health probes, and inbound calls from third parties that authenticate
# themselves (webhook signatures/secrets) or are OAuth redirects.
_PUBLIC_EXACT = {
    "/api/system/health",
    "/api/remote/hello",  # discovery probe; reports whether the caller is authorized
    "/api/spotify/callback",
    "/api/health/oauth/callback",
    "/api/integrations/workspace/google/oauth/callback",
}
_PUBLIC_PREFIXES = ("/api/channels/", "/api/health/webhook/")


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def is_remote(headers: list[tuple[bytes, bytes]], client_host: str | None, require_token_on_lan: bool) -> bool:
    for name, _ in headers:
        lowered = name.lower()
        if lowered in _PROXY_HEADERS or lowered.startswith(b"tailscale-"):
            return True
    return require_token_on_lan and not _is_loopback(client_host)


def needs_token(path: str) -> bool:
    if not path.startswith("/api/"):
        return False  # static UI and add-in files are public; their API calls are not
    if path in _PUBLIC_EXACT:
        return False
    return not path.startswith(_PUBLIC_PREFIXES)


def _header(scope, wanted: bytes) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() == wanted:
            return value.decode("latin-1").strip()
    return None


def _presented_token(scope) -> str:
    header = _header(scope, TOKEN_HEADER)
    if header is not None:
        return header
    query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    return (query.get(TOKEN_QUERY) or [""])[0].strip()


def tailscale_login(scope, own_ips: frozenset[str] = frozenset()) -> str:
    """The tailnet user behind a request proxied by tailscaled on this machine, else ''.

    Only a connection from tailscaled itself counts, since it strips client-sent
    Tailscale-* headers: loopback, or this machine's own Tailscale IP (tailscaled
    on Windows connects from that). From any other address the header could be forged.
    """
    client = scope.get("client")
    peer = client[0] if client else None
    if not (_is_loopback(peer) or peer in own_ips):
        return ""
    if _header(scope, b"tailscale-funnel-request") is not None:
        return ""  # public internet via Funnel: no identity
    return (_header(scope, b"tailscale-user-login") or "").lower()


async def authorization(scope, require_token_on_lan: bool = False) -> str:
    """How a request is allowed in: 'local', 'tailscale', 'token' — or '' if it isn't."""
    client = scope.get("client")
    if not is_remote(scope.get("headers", []), client[0] if client else None, require_token_on_lan):
        return "local"
    login = tailscale_login(scope, await own_tailscale_ips())
    if login and login in await trusted_logins():
        return "tailscale"
    if token_ok(_presented_token(scope)):
        return "token"
    return ""


class RemoteAccessMiddleware:
    """Pure ASGI so streaming responses (SSE) pass through untouched."""

    def __init__(self, app, require_token_on_lan: bool = False):
        self.app = app
        self.require_token_on_lan = require_token_on_lan

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)  # CORS preflight carries no credentials

        path = scope.get("path", "")
        if not needs_token(path) or await authorization(scope, self.require_token_on_lan):
            return await self.app(scope, receive, send)

        client = scope.get("client")
        login = _header(scope, b"tailscale-user-login")
        logger.warning(
            "Rejected remote %s %s from %s (Tailscale login: %s): not a trusted Tailscale user and no valid access token",
            scope.get("method", "WS"), path, client[0] if client else "unknown", login or "none sent",
        )
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})
            return
        body = json.dumps({
            "detail": "This Luna only lets in its owner's Tailscale devices without a token. "
                      "Use the access token from data/local_api_token on the server (printed by `luna serve --tailscale`).",
            "code": "remote_token_required",
        }).encode()
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
