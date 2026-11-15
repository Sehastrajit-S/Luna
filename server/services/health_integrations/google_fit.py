"""Google Fit OAuth2 and sync."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.health_integrations.db import _update_sync, persist
from backend.services.health_integrations.models import (
    ACTIVE_MINUTES, BLOOD_OXYGEN, BODY_FAT_PCT, CALORIES, DISTANCE_KM,
    HEART_RATE, SLEEP_DURATION, STEPS, WEIGHT_KG,
    HealthIntegrationError, HealthMetricPoint,
)
from backend.services.health_integrations.oauth import _get, _oauth_refresh, _post_json

log = logging.getLogger(__name__)

GOOGLE_FIT_BASE      = "https://www.googleapis.com/fitness/v1/users/me"
GOOGLE_FIT_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_FIT_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_FIT_SCOPES    = " ".join([
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.blood_glucose.read",
    "https://www.googleapis.com/auth/fitness.blood_pressure.read",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.read",
])


def google_fit_is_configured() -> bool:
    return bool(settings.google_fit_client_id and settings.google_fit_access_token)


async def _google_fit_token() -> str:
    if not google_fit_is_configured():
        raise HealthIntegrationError("Google Fit not configured — set google_fit_client_id, google_fit_access_token in .env")
    if settings.google_fit_refresh_token:
        try:
            data = await _oauth_refresh(
                GOOGLE_FIT_TOKEN_URL,
                settings.google_fit_client_id,
                settings.google_fit_client_secret,
                settings.google_fit_refresh_token,
            )
            import os
            os.environ["GOOGLE_FIT_ACCESS_TOKEN"] = data.get("access_token", "")
            return data["access_token"]
        except Exception:
            pass
    return settings.google_fit_access_token


async def google_fit_oauth_url(redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id":     settings.google_fit_client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         GOOGLE_FIT_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    return f"{GOOGLE_FIT_AUTH_URL}?{urlencode(params)}"


async def google_fit_exchange_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GOOGLE_FIT_TOKEN_URL, data={
            "client_id":     settings.google_fit_client_id,
            "client_secret": settings.google_fit_client_secret,
            "code":          code,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        })
    resp.raise_for_status()
    return resp.json()


def _day_millis(day: str) -> tuple[int, int]:
    d     = date.fromisoformat(day)
    start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)
    end   = start + 86_400_000
    return start, end


async def google_fit_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    token = await _google_fit_token()
    d     = target_date or date.today().isoformat()
    start_ms, end_ms = _day_millis(d)
    points: list[HealthMetricPoint] = []

    data_type_map = {
        "com.google.step_count.delta":      (STEPS, "steps"),
        "com.google.distance.delta":        (DISTANCE_KM, "km"),
        "com.google.calories.expended":     (CALORIES, "kcal"),
        "com.google.heart_rate.bpm":        (HEART_RATE, "bpm"),
        "com.google.weight":                (WEIGHT_KG, "kg"),
        "com.google.body.fat.percentage":   (BODY_FAT_PCT, "%"),
        "com.google.active_minutes":        (ACTIVE_MINUTES, "min"),
        "com.google.oxygen_saturation":     (BLOOD_OXYGEN, "%"),
        "com.google.blood_pressure":        (None, None),
    }

    body = {
        "aggregateBy":  [{"dataTypeName": k} for k in data_type_map],
        "startTimeMillis": start_ms,
        "endTimeMillis":   end_ms,
        "bucketByTime":    {"durationMillis": 86_400_000},
    }

    try:
        resp = await _post_json(f"{GOOGLE_FIT_BASE}/dataset:aggregate", token, body)
        for bucket in resp.get("bucket", []):
            for ds in bucket.get("dataset", []):
                dtype = ds.get("dataSourceId", "")
                matched_metric = matched_unit = None
                for k, (m, u) in data_type_map.items():
                    if k in dtype and m:
                        matched_metric, matched_unit = m, u
                        break
                if not matched_metric:
                    continue
                for pt in ds.get("point", []):
                    for val in pt.get("value", []):
                        raw_val = val.get("fpVal") or val.get("intVal")
                        if raw_val is not None:
                            if matched_metric == DISTANCE_KM:
                                raw_val = float(raw_val) / 1000.0
                            points.append(HealthMetricPoint("google_fit", matched_metric, float(raw_val), matched_unit, d))
    except Exception as e:
        log.warning("Google Fit aggregate: %s", e)

    try:
        sessions_resp = await _get(
            f"{GOOGLE_FIT_BASE}/sessions",
            token,
            params={
                "startTime":  f"{d}T00:00:00.000Z",
                "endTime":    f"{d}T23:59:59.000Z",
                "activityType": "72",
            },
        )
        total_sleep = 0
        for s in sessions_resp.get("session", []):
            start_ns = int(s.get("startTimeMillis", 0))
            end_ns   = int(s.get("endTimeMillis",   0))
            total_sleep += (end_ns - start_ns) // 60000
        if total_sleep:
            points.append(HealthMetricPoint("google_fit", SLEEP_DURATION, float(total_sleep), "min", d))
    except Exception as e:
        log.warning("Google Fit sleep: %s", e)

    count = persist(db, points)
    _update_sync(db, "google_fit", "ok", count)
    return points


# ── Integration class (auto-discovered by sync.py) ────────────────────────────

from backend.services.health_integrations.base import EnvField, HealthIntegration, IntegrationManifest  # noqa: E402


class GoogleFitIntegration(HealthIntegration):
    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            id="google_fit", name="Google Fit",
            description="Activity, calories, heart rate, sleep, body metrics",
            auth_type="oauth",
            env_fields=[
                EnvField("GOOGLE_FIT_CLIENT_ID",     "Client ID",     placeholder="your-id.apps.googleusercontent.com"),
                EnvField("GOOGLE_FIT_CLIENT_SECRET", "Client Secret", secret=True, placeholder="GOCSPX-..."),
            ],
            help_text=(
                "1. Go to console.cloud.google.com → enable the Fitness API\n"
                "2. Create OAuth 2.0 credentials (Desktop app)\n"
                "3. Set redirect URI to:\n"
                "   http://127.0.0.1:8899/api/health/oauth/callback\n"
                "4. Copy Client ID and Secret, then click Connect"
            ),
            help_url="https://console.cloud.google.com",
        )

    def is_configured(self) -> bool:
        return google_fit_is_configured()

    async def sync(self, db, target_date=None):
        return await google_fit_sync(db, target_date)

    async def oauth_url(self, redirect_uri):
        return await google_fit_oauth_url(redirect_uri)

    async def exchange_code(self, code, redirect_uri):
        return await google_fit_exchange_code(code, redirect_uri)
