import urllib.parse

import httpx
from fastapi import APIRouter, Body, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.config import BASE_DIR, settings
from backend.services.audit_log import record_audit
from backend.services.workspace_integrations import (
    WorkspaceIntegrationError,
    google_workspace,
    integration_status,
    microsoft_workspace,
)

router = APIRouter(prefix="/api/integrations/workspace", tags=["workspace-integrations"])

_GOOGLE_REDIRECT_URI = "http://127.0.0.1:8899/api/integrations/workspace/google/oauth/callback"
_GOOGLE_SCOPES = " ".join([
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts.readonly",
])


def _patch_env(key: str, value: str) -> None:
    """Write/update a single key in .env and update the live settings object."""
    env_file = BASE_DIR / ".env"
    try:
        text = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
        import re
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        line = f"{key}={value}"
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            text = text.rstrip("\n") + f"\n{line}\n"
        env_file.write_text(text, encoding="utf-8")
    except Exception:
        pass
    setattr(settings, key, value)


@router.get("/google/oauth/start")
def google_oauth_start():
    if not settings.google_workspace_client_id:
        return JSONResponse({"error": "google_workspace_client_id not set in .env"}, status_code=400)
    qs = urllib.parse.urlencode({
        "client_id":     settings.google_workspace_client_id,
        "redirect_uri":  _GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         _GOOGLE_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{qs}")


@router.get("/google/oauth/callback")
async def google_oauth_callback(code: str = "", error: str = ""):
    if error:
        return HTMLResponse(f"<h2>OAuth error: {error}</h2>", status_code=400)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code":          code,
            "client_id":     settings.google_workspace_client_id,
            "client_secret": settings.google_workspace_client_secret,
            "redirect_uri":  _GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        })
    if resp.is_error:
        return HTMLResponse(f"<h2>Token exchange failed</h2><pre>{resp.text}</pre>", status_code=400)
    tokens = resp.json()
    refresh = tokens.get("refresh_token", "")
    access  = tokens.get("access_token", "")
    if refresh:
        _patch_env("google_workspace_refresh_token", refresh)
    if access:
        _patch_env("google_workspace_access_token", access)
    return HTMLResponse("""
        <html><body style="font-family:sans-serif;padding:40px;background:#09090f;color:#eef2ff">
        <h2 style="color:#a78bfa">Google Workspace connected!</h2>
        <p>Tokens saved. You can close this window and return to Luna.</p>
        </body></html>
    """)


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix):].strip()
    return authorization.strip()


@router.get("/status")
def status():
    return integration_status()


@router.post("/google/{service}/{action}")
async def google_action(
    service: str,
    action: str,
    payload: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    try:
        result = await google_workspace(service, action, payload, _token_from_header(authorization))
        record_audit(
            "google_workspace",
            args={"service": service, "action": action},
            result=str(result.data)[:500],
            status="ok",
        )
        return result.as_dict()
    except WorkspaceIntegrationError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@router.post("/microsoft/{service}/{action}")
async def microsoft_action(
    service: str,
    action: str,
    payload: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    try:
        result = await microsoft_workspace(service, action, payload, _token_from_header(authorization))
        record_audit(
            "microsoft_workspace",
            args={"service": service, "action": action},
            result=str(result.data)[:500],
            status="ok",
        )
        return result.as_dict()
    except WorkspaceIntegrationError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)
