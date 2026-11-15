"""
Health integration router.

Endpoints
---------
GET  /api/health/status                     — configured platforms + last sync state
GET  /api/health/metrics                    — query stored metrics (platform/type/date filters)
GET  /api/health/summary?date=YYYY-MM-DD    — aggregated daily summary across all platforms
POST /api/health/sync?platform=&date=       — trigger sync (all or one platform)
GET  /api/health/oauth/authorize/{platform} — start OAuth2 flow (Fitbit / Google Fit / Withings)
GET  /api/health/oauth/callback             — handle OAuth2 redirect
POST /api/health/webhook/{platform}         — inbound webhook (apple / samsung)
"""

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db
from backend.services.health_integrations import (
    PLATFORM_CONFIGURED,
    PLATFORM_OAUTH,
    PLATFORM_SYNC,
    HealthIntegrationError,
    daily_summary,
    integration_status,
    parse_apple_health_export,
    parse_samsung_health_export,
    query_metrics,
    sync_all,
)

router = APIRouter(prefix="/api/health", tags=["health"])

# ── Status ────────────────────────────────────────────────────────────────


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return integration_status(db)


# ── Metrics query ─────────────────────────────────────────────────────────


@router.get("/metrics")
def get_metrics(
    platform: Optional[str] = Query(None),
    metric_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    return {
        "metrics": query_metrics(db, platform, metric_type, from_date, to_date, limit)
    }


@router.get("/summary")
def get_summary(
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
):
    d = date or date_cls.today().isoformat()
    return daily_summary(db, d)


# ── Sync ──────────────────────────────────────────────────────────────────


@router.post("/sync")
async def trigger_sync(
    platform: Optional[str] = Query(None, description="Platform name or omit for all"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
):
    if platform:
        platform = platform.lower()
        if platform not in PLATFORM_CONFIGURED:
            raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}. Valid: {list(PLATFORM_CONFIGURED)}")
        if platform in ("apple", "samsung"):
            raise HTTPException(status_code=400, detail=f"{platform} uses webhooks — POST data to /api/health/webhook/{platform}")
        if not PLATFORM_CONFIGURED[platform]():
            raise HTTPException(status_code=400, detail=f"{platform} is not configured — add credentials to .env")
        try:
            pts = await PLATFORM_SYNC[platform](db, date)
            return {"platform": platform, "synced": len(pts)}
        except HealthIntegrationError as e:
            raise HTTPException(status_code=502, detail=str(e))
    else:
        results = await sync_all(db, date)
        return {"results": results, "total": sum(v for v in results.values() if v > 0)}


# ── OAuth2 ────────────────────────────────────────────────────────────────


@router.get("/oauth/authorize/{platform}")
async def oauth_authorize(platform: str, request: Request):
    platform = platform.lower()
    if platform not in PLATFORM_OAUTH:
        raise HTTPException(status_code=400, detail=f"{platform} does not use OAuth2 — valid: {list(PLATFORM_OAUTH)}")
    if not PLATFORM_CONFIGURED.get(platform, lambda: False)() and not getattr(settings, f"{platform.replace('_', '_')}_client_id", ""):
        raise HTTPException(status_code=400, detail=f"{platform} client_id not configured in .env")

    redirect_uri = str(request.url_for("oauth_callback")).replace("http://", "https://")
    oauth_url_fn, _ = PLATFORM_OAUTH[platform]
    url = await oauth_url_fn(redirect_uri)
    # Store platform in a cookie so the callback knows which one to complete
    response = RedirectResponse(url)
    response.set_cookie("health_oauth_platform", platform, max_age=600, httponly=True)
    return response


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
):
    platform = request.cookies.get("health_oauth_platform")
    if not platform or platform not in PLATFORM_OAUTH:
        raise HTTPException(status_code=400, detail="OAuth state lost — restart the authorization flow")

    redirect_uri = str(request.url_for("oauth_callback")).replace("http://", "https://")
    _, exchange_fn = PLATFORM_OAUTH[platform]
    try:
        token_data = await exchange_fn(code, redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {e}")

    access = token_data.get("access_token", "")
    refresh = token_data.get("refresh_token", "")
    hint = []
    if access:
        hint.append(f"{platform.upper()}_ACCESS_TOKEN={access}")
    if refresh:
        hint.append(f"{platform.upper()}_REFRESH_TOKEN={refresh}")

    return {
        "ok": True,
        "platform": platform,
        "message": "Authorization successful. Save these values to your .env file:",
        "env_vars": hint,
        "access_token": access,
        "refresh_token": refresh,
    }


# ── Webhooks (Apple Health / Samsung Health) ──────────────────────────────


def _verify_webhook_secret(secret: Optional[str]) -> None:
    expected = settings.health_webhook_secret
    if not expected:
        return  # no secret configured — open endpoint
    if secret != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


@router.post("/webhook/apple")
async def apple_webhook(
    payload: dict = Body(...),
    x_health_secret: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Receive Apple Health data pushed by the 'Health Auto Export' iOS app.

    iOS app setup:
    1. Install 'Health Auto Export' on iPhone (free tier works)
    2. Add custom export → HTTP endpoint: POST {luna_url}/api/health/webhook/apple
    3. Set header: X-Health-Secret: <your health_webhook_secret>
    4. Enable auto-export on schedule or on open
    """
    _verify_webhook_secret(x_health_secret)
    try:
        points = parse_apple_health_export(payload, db)
        return {"ok": True, "received": len(points), "platform": "apple"}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parse error: {e}")


@router.post("/webhook/samsung")
async def samsung_webhook(
    payload: dict = Body(...),
    x_health_secret: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Receive Samsung Health data from a compatible exporter app.

    Compatible exporters:
    - Health Export for Samsung (Android)
    - Any app that can POST Health Auto Export-compatible JSON
    - Custom Tasker/Automate flows reading Samsung Health DB

    Endpoint: POST {luna_url}/api/health/webhook/samsung
    Header: X-Health-Secret: <your health_webhook_secret>
    """
    _verify_webhook_secret(x_health_secret)
    try:
        points = parse_samsung_health_export(payload, db)
        return {"ok": True, "received": len(points), "platform": "samsung"}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parse error: {e}")


# ── Metric type reference ─────────────────────────────────────────────────


@router.get("/metric-types")
def metric_types():
    from backend.services.health_integrations import METRIC_UNITS
    return {
        "metric_types": [
            {"type": k, "unit": v}
            for k, v in METRIC_UNITS.items()
        ]
    }


# ── Integration manifests ─────────────────────────────────────────────────


@router.get("/manifests")
def integration_manifests():
    """Return metadata for every auto-discovered integration.

    The settings UI uses this to render integration cards and setup forms
    without any frontend code changes when a new integration is added.
    """
    from backend.services.health_integrations.sync import _PLATFORMS
    webhook = {"apple", "samsung"}
    platforms = []
    for pid, p in _PLATFORMS.items():
        m = p.manifest
        platforms.append({
            "id":          m.id,
            "name":        m.name,
            "description": m.description,
            "auth_type":   m.auth_type,
            "configured":  p.is_configured(),
            "env_fields": [
                {
                    "key":         f.key,
                    "label":       f.label,
                    "secret":      f.secret,
                    "placeholder": f.placeholder,
                    "required":    f.required,
                }
                for f in m.env_fields
            ],
            "help_text": m.help_text,
            "help_url":  m.help_url,
        })
    # Include webhook-only platforms that aren't auto-discovered
    for name in webhook:
        if name not in _PLATFORMS:
            platforms.append({
                "id": name, "name": name.title(),
                "description": f"{name.title()} Health (webhook push)",
                "auth_type": "webhook", "configured": True,
                "env_fields": [], "help_text": "", "help_url": "",
            })
    return {"platforms": platforms}
