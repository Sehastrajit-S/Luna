"""Withings OAuth2 and sync."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.health_integrations.db import _update_sync, persist
from backend.services.health_integrations.models import (
    BMI, BODY_FAT_PCT, BP_DIASTOLIC, BP_SYSTOLIC, HEART_RATE,
    SLEEP_DURATION, SLEEP_SCORE, WEIGHT_KG,
    HealthIntegrationError, HealthMetricPoint,
)

log = logging.getLogger(__name__)

WITHINGS_BASE      = "https://wbsapi.withings.net"
WITHINGS_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
WITHINGS_AUTH_URL  = "https://account.withings.com/oauth2_user/authorize2"

_WITHINGS_WEIGHT     = 1
_WITHINGS_BMI        = 35
_WITHINGS_FAT_PCT    = 6
_WITHINGS_BP_DIASTOL = 9
_WITHINGS_BP_SYSTOL  = 10
_WITHINGS_HR         = 11


def withings_is_configured() -> bool:
    return bool(settings.withings_client_id and settings.withings_access_token)


async def _withings_token() -> str:
    if not withings_is_configured():
        raise HealthIntegrationError("Withings not configured — set withings_client_id, withings_access_token in .env")
    if settings.withings_refresh_token:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(WITHINGS_TOKEN_URL, data={
                    "action":        "requesttoken",
                    "grant_type":    "refresh_token",
                    "client_id":     settings.withings_client_id,
                    "client_secret": settings.withings_client_secret,
                    "refresh_token": settings.withings_refresh_token,
                })
            resp.raise_for_status()
            data = resp.json().get("body", {})
            import os
            os.environ["WITHINGS_ACCESS_TOKEN"] = data.get("access_token", "")
            if data.get("refresh_token"):
                os.environ["WITHINGS_REFRESH_TOKEN"] = data["refresh_token"]
            return data["access_token"]
        except Exception:
            pass
    return settings.withings_access_token


async def withings_oauth_url(redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id":     settings.withings_client_id,
        "redirect_uri":  redirect_uri,
        "scope":         "user.info,user.metrics,user.activity",
        "state":         "luna",
    }
    return f"{WITHINGS_AUTH_URL}?{urlencode(params)}"


async def withings_exchange_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(WITHINGS_TOKEN_URL, data={
            "action":        "requesttoken",
            "grant_type":    "authorization_code",
            "client_id":     settings.withings_client_id,
            "client_secret": settings.withings_client_secret,
            "code":          code,
            "redirect_uri":  redirect_uri,
        })
    resp.raise_for_status()
    return resp.json().get("body", {})


async def withings_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    token  = await _withings_token()
    d      = target_date or date.today().isoformat()
    d_obj  = date.fromisoformat(d)
    start_ts = int(datetime(d_obj.year, d_obj.month, d_obj.day, tzinfo=timezone.utc).timestamp())
    end_ts   = start_ts + 86400
    points: list[HealthMetricPoint] = []

    type_map = {
        _WITHINGS_WEIGHT:     (WEIGHT_KG,    "kg",   1),
        _WITHINGS_BMI:        (BMI,          "kg/m2",1),
        _WITHINGS_FAT_PCT:    (BODY_FAT_PCT, "%",    1),
        _WITHINGS_BP_DIASTOL: (BP_DIASTOLIC, "mmHg", 1),
        _WITHINGS_BP_SYSTOL:  (BP_SYSTOLIC,  "mmHg", 1),
        _WITHINGS_HR:         (HEART_RATE,   "bpm",  1),
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{WITHINGS_BASE}/measure",
                headers={"Authorization": f"Bearer {token}"},
                params={"action": "getmeas", "startdate": start_ts, "enddate": end_ts, "category": 1},
            )
        resp.raise_for_status()
        groups = resp.json().get("body", {}).get("measuregrps", [])
        for grp in groups:
            for meas in grp.get("measures", []):
                mtype = meas.get("type")
                if mtype in type_map:
                    metric, unit, _ = type_map[mtype]
                    val = meas["value"] * (10 ** meas.get("unit", 0))
                    points.append(HealthMetricPoint("withings", metric, float(val), unit, d))
    except Exception as e:
        log.warning("Withings measures: %s", e)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{WITHINGS_BASE}/v2/sleep",
                headers={"Authorization": f"Bearer {token}"},
                params={"action": "getsummary", "startdateymd": d, "enddateymd": d},
            )
        resp.raise_for_status()
        for s in resp.json().get("body", {}).get("series", []):
            data = s.get("data", {})
            if "nb_rem_episodes" in data:
                duration = data.get("total_sleep_time", 0)
                points.append(HealthMetricPoint("withings", SLEEP_DURATION, float(duration) / 60, "min", d))
                if "sleep_score" in data:
                    points.append(HealthMetricPoint("withings", SLEEP_SCORE, float(data["sleep_score"]), "score", d))
    except Exception as e:
        log.warning("Withings sleep: %s", e)

    count = persist(db, points)
    _update_sync(db, "withings", "ok", count)
    return points


# ── Integration class (auto-discovered by sync.py) ────────────────────────────

from backend.services.health_integrations.base import EnvField, HealthIntegration, IntegrationManifest  # noqa: E402


class WithingsIntegration(HealthIntegration):
    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            id="withings", name="Withings",
            description="Weight, blood pressure, sleep, body composition",
            auth_type="oauth",
            env_fields=[
                EnvField("WITHINGS_CLIENT_ID",     "Client ID",     placeholder="your-withings-client-id"),
                EnvField("WITHINGS_CLIENT_SECRET", "Client Secret", secret=True, placeholder="your-withings-client-secret"),
            ],
            help_text=(
                "1. Go to developer.withings.com → Create an application\n"
                "2. Set redirect URI to:\n"
                "   http://127.0.0.1:8899/api/health/oauth/callback\n"
                "3. Copy Client ID and Secret, then click Connect"
            ),
            help_url="https://developer.withings.com",
        )

    def is_configured(self) -> bool:
        return withings_is_configured()

    async def sync(self, db, target_date=None):
        return await withings_sync(db, target_date)

    async def oauth_url(self, redirect_uri):
        return await withings_oauth_url(redirect_uri)

    async def exchange_code(self, code, redirect_uri):
        return await withings_exchange_code(code, redirect_uri)
