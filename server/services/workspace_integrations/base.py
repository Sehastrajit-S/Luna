"""Shared types, helpers, and OAuth token resolution."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

import httpx

from server.config import settings


class WorkspaceIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceResponse:
    provider: str
    service: str
    action: str
    data: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "service": self.service,
            "action": self.action,
            "data": self.data,
        }


GOOGLE_BASES = {
    "gmail":    "https://gmail.googleapis.com/gmail/v1",
    "calendar": "https://www.googleapis.com/calendar/v3",
    "drive":    "https://www.googleapis.com/drive/v3",
    "docs":     "https://docs.googleapis.com/v1",
    "sheets":   "https://sheets.googleapis.com/v4",
    "slides":   "https://slides.googleapis.com/v1",
    "tasks":    "https://tasks.googleapis.com/tasks/v1",
    "people":   "https://people.googleapis.com/v1",
}

MICROSOFT_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _configured_token(provider: str) -> str:
    if provider == "google":
        return settings.google_workspace_access_token.strip()
    if provider == "microsoft":
        return settings.microsoft_workspace_access_token.strip()
    return ""


async def _refresh_google_token() -> str:
    if not (
        settings.google_workspace_client_id
        and settings.google_workspace_client_secret
        and settings.google_workspace_refresh_token
    ):
        return ""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     settings.google_workspace_client_id,
                "client_secret": settings.google_workspace_client_secret,
                "refresh_token": settings.google_workspace_refresh_token,
                "grant_type":    "refresh_token",
            },
        )
    if response.is_error:
        if "invalid_grant" in response.text:
            raise WorkspaceIntegrationError(
                "Google sign-in has expired or was revoked. Reconnect Google: open "
                f"http://127.0.0.1:{settings.port}/api/integrations/workspace/google/oauth/start on this computer.")
        raise WorkspaceIntegrationError(
            f"google OAuth refresh failed {response.status_code}: {response.text[:300]}"
        )
    return _remember("google", response.json())


async def _refresh_microsoft_token() -> str:
    if not (
        settings.microsoft_workspace_client_id
        and settings.microsoft_workspace_client_secret
        and settings.microsoft_workspace_refresh_token
    ):
        return ""
    tenant = settings.microsoft_workspace_tenant_id or "common"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id":     settings.microsoft_workspace_client_id,
                "client_secret": settings.microsoft_workspace_client_secret,
                "refresh_token": settings.microsoft_workspace_refresh_token,
                "grant_type":    "refresh_token",
            },
        )
    if response.is_error:
        raise WorkspaceIntegrationError(
            f"microsoft OAuth refresh failed {response.status_code}: {response.text[:300]}"
        )
    return _remember("microsoft", response.json())


# provider → (access token, monotonic time it stops being used). Access tokens last about an hour;
# the one saved in .env expires too, so it is only the fallback when no refresh token is set.
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _remember(provider: str, payload: dict) -> str:
    import time
    access_token = str(payload.get("access_token") or "")
    if access_token:
        lifetime = float(payload.get("expires_in") or 3600)
        _TOKEN_CACHE[provider] = (access_token, time.monotonic() + max(60.0, lifetime - 120))
    return access_token


async def _resolved_token(provider: str, token: str = "", *, force_refresh: bool = False) -> str:
    import time
    if token.strip():
        return token.strip()   # passed in explicitly by the caller
    cached = _TOKEN_CACHE.get(provider)
    if cached and not force_refresh and time.monotonic() < cached[1]:
        return cached[0]
    refresh = {"google": _refresh_google_token, "microsoft": _refresh_microsoft_token}.get(provider)
    access_token = await refresh() if refresh else ""
    if not access_token and not force_refresh:
        access_token = _configured_token(provider)   # no refresh token: the saved one, while it lasts
    if not access_token:
        raise WorkspaceIntegrationError(f"{provider} workspace access token is not configured")
    return access_token


async def _headers(provider: str, token: str = "", *, force_refresh: bool = False) -> dict[str, str]:
    access_token = await _resolved_token(provider, token, force_refresh=force_refresh)
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def _request(
    method: str,
    url: str,
    provider: str,
    token: str = "",
    params: dict[str, Any] | None = None,
    json_body: Any = None,
) -> Any:
    clean_params = {k: v for k, v in params.items() if v is not None} if params else None
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(
            method.upper(),
            url,
            headers=await _headers(provider, token),
            params=clean_params or None,
            json=json_body,
        )
        if response.status_code == 401 and not token:
            # Expired access token: get a fresh one with the refresh token and try once more.
            _TOKEN_CACHE.pop(provider, None)
            try:
                headers = await _headers(provider, force_refresh=True)
            except WorkspaceIntegrationError:
                headers = None
            if headers:
                response = await client.request(method.upper(), url, headers=headers,
                                                params=clean_params or None, json=json_body)
    if response.status_code == 401:
        raise WorkspaceIntegrationError(
            f"{provider} sign-in has expired and couldn't be renewed. Reconnect {provider.title()} in Settings.")
    if response.status_code == 204:
        return {"status": "ok"}
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text}
    if response.is_error:
        detail = data.get("error", data) if isinstance(data, dict) else data
        raise WorkspaceIntegrationError(f"{provider} API error {response.status_code}: {detail}")
    return data


def _clean_path(path: str) -> str:
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    if "://" in path:
        raise WorkspaceIntegrationError("raw paths must be relative API paths, not full URLs")
    return path


def _gmail_raw_message(to: str, subject: str, body: str, sender: str = "") -> str:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if sender:
        message["From"] = sender
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")


def integration_status() -> dict[str, Any]:
    return {
        "google": {
            "configured": bool(
                settings.google_workspace_access_token or settings.google_workspace_refresh_token
            ),
            "services": sorted(GOOGLE_BASES),
        },
        "microsoft": {
            "configured": bool(
                settings.microsoft_workspace_access_token or settings.microsoft_workspace_refresh_token
            ),
            "services": ["profile", "mail", "calendar", "drive", "todo", "excel", "teams", "graph"],
        },
    }
