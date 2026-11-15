"""Settings API shared by Luna's UIs. Reads are masked; writes need the local token."""
from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException

from backend.services.settings_store import SettingsError, read_settings, token_ok, update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    return await read_settings()


@router.put("")
async def put_settings(changes: dict = Body(...), x_luna_token: str | None = Header(default=None)):
    # CORS alone can't protect this: sandboxed iframes on any site also send
    # Origin: null. The token lives in data/ where only local apps can read it.
    if not token_ok(x_luna_token):
        raise HTTPException(status_code=403, detail="Missing or invalid local access token.")
    try:
        return update_settings(changes)
    except SettingsError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
