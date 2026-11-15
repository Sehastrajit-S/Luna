"""Fitbit OAuth2 and sync."""
from __future__ import annotations

import base64
import logging
from datetime import date
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.health_integrations.db import _update_sync, persist
from backend.services.health_integrations.models import (
    ACTIVE_MINUTES, BLOOD_OXYGEN, CALORIES, DISTANCE_KM, HRV,
    RESTING_HR, RESPIRATORY_RATE, SKIN_TEMP, SLEEP_AWAKE, SLEEP_DEEP,
    SLEEP_DURATION, SLEEP_LIGHT, SLEEP_REM, STEPS, WEIGHT_KG,
    HealthIntegrationError, HealthMetricPoint,
)
from backend.services.health_integrations.oauth import _get, _oauth_refresh

log = logging.getLogger(__name__)

FITBIT_BASE      = "https://api.fitbit.com"
FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
FITBIT_AUTH_URL  = "https://www.fitbit.com/oauth2/authorize"
FITBIT_SCOPES    = "activity heartrate sleep weight oxygen_saturation respiratory_rate temperature"


def fitbit_is_configured() -> bool:
    return bool(settings.fitbit_client_id and settings.fitbit_access_token)


async def _fitbit_token() -> str:
    if not fitbit_is_configured():
        raise HealthIntegrationError("Fitbit not configured — set fitbit_client_id, fitbit_access_token in .env")
    if settings.fitbit_refresh_token:
        try:
            data = await _oauth_refresh(
                FITBIT_TOKEN_URL,
                settings.fitbit_client_id,
                settings.fitbit_client_secret,
                settings.fitbit_refresh_token,
            )
            import os
            os.environ["FITBIT_ACCESS_TOKEN"] = data.get("access_token", "")
            if data.get("refresh_token"):
                os.environ["FITBIT_REFRESH_TOKEN"] = data["refresh_token"]
            return data["access_token"]
        except Exception:
            pass
    return settings.fitbit_access_token


async def fitbit_oauth_url(redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id":     settings.fitbit_client_id,
        "redirect_uri":  redirect_uri,
        "scope":         FITBIT_SCOPES,
    }
    return f"{FITBIT_AUTH_URL}?{urlencode(params)}"


async def fitbit_exchange_code(code: str, redirect_uri: str) -> dict:
    auth = base64.b64encode(f"{settings.fitbit_client_id}:{settings.fitbit_client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            FITBIT_TOKEN_URL,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
    resp.raise_for_status()
    return resp.json()


async def fitbit_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    token = await _fitbit_token()
    d = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []

    async def _fetch(path: str) -> dict:
        return await _get(f"{FITBIT_BASE}{path}", token)

    try:
        acts    = await _fetch(f"/1/user/-/activities/date/{d}.json")
        summary = acts.get("summary", {})
        if "steps" in summary:
            points.append(HealthMetricPoint("fitbit", STEPS, float(summary["steps"]), "steps", d))
        if "distances" in summary:
            for dist in summary["distances"]:
                if dist.get("activity") == "total":
                    points.append(HealthMetricPoint("fitbit", DISTANCE_KM, float(dist["distance"]), "km", d))
        if "caloriesOut" in summary:
            points.append(HealthMetricPoint("fitbit", CALORIES, float(summary["caloriesOut"]), "kcal", d))
        if "veryActiveMinutes" in summary and "fairlyActiveMinutes" in summary:
            active = summary["veryActiveMinutes"] + summary["fairlyActiveMinutes"]
            points.append(HealthMetricPoint("fitbit", ACTIVE_MINUTES, float(active), "min", d))
    except Exception as e:
        log.warning("Fitbit activities: %s", e)

    try:
        hr     = await _fetch(f"/1/user/-/activities/heart/date/{d}/1d.json")
        hr_val = hr.get("activities-heart", [{}])[0].get("value", {})
        if "restingHeartRate" in hr_val:
            points.append(HealthMetricPoint("fitbit", RESTING_HR, float(hr_val["restingHeartRate"]), "bpm", d))
    except Exception as e:
        log.warning("Fitbit heart rate: %s", e)

    try:
        sleep = await _fetch(f"/1.2/user/-/sleep/date/{d}.json")
        for s in sleep.get("sleep", []):
            if s.get("isMainSleep"):
                lsummary = s.get("levels", {}).get("summary", {})
                duration = s.get("minutesAsleep", 0)
                points.append(HealthMetricPoint("fitbit", SLEEP_DURATION, float(duration), "min", d))
                if "deep"  in lsummary: points.append(HealthMetricPoint("fitbit", SLEEP_DEEP,  float(lsummary["deep"]["minutes"]),  "min", d))
                if "rem"   in lsummary: points.append(HealthMetricPoint("fitbit", SLEEP_REM,   float(lsummary["rem"]["minutes"]),   "min", d))
                if "light" in lsummary: points.append(HealthMetricPoint("fitbit", SLEEP_LIGHT, float(lsummary["light"]["minutes"]), "min", d))
                if "wake"  in lsummary: points.append(HealthMetricPoint("fitbit", SLEEP_AWAKE, float(lsummary["wake"]["minutes"]),  "min", d))
    except Exception as e:
        log.warning("Fitbit sleep: %s", e)

    try:
        spo2 = await _fetch(f"/1/user/-/spo2/date/{d}.json")
        val  = spo2.get("value", {}).get("avg")
        if val is not None:
            points.append(HealthMetricPoint("fitbit", BLOOD_OXYGEN, float(val), "%", d))
    except Exception as e:
        log.warning("Fitbit SpO2: %s", e)

    try:
        hrv = await _fetch(f"/1/user/-/hrv/date/{d}.json")
        for entry in hrv.get("hrv", []):
            val = entry.get("value", {}).get("dailyRmssd")
            if val is not None:
                points.append(HealthMetricPoint("fitbit", HRV, float(val), "ms", d))
    except Exception as e:
        log.warning("Fitbit HRV: %s", e)

    try:
        br = await _fetch(f"/1/user/-/br/date/{d}.json")
        for entry in br.get("br", []):
            val = entry.get("value", {}).get("breathingRate")
            if val is not None:
                points.append(HealthMetricPoint("fitbit", RESPIRATORY_RATE, float(val), "rpm", d))
    except Exception as e:
        log.warning("Fitbit breathing rate: %s", e)

    try:
        temp = await _fetch(f"/1/user/-/temp/skin/date/{d}.json")
        for entry in temp.get("tempSkin", []):
            val = entry.get("value", {}).get("nightlyRelative")
            if val is not None:
                points.append(HealthMetricPoint("fitbit", SKIN_TEMP, float(val), "°C", d))
    except Exception as e:
        log.warning("Fitbit skin temp: %s", e)

    try:
        weight  = await _fetch(f"/1/user/-/body/weight/date/{d}/1d.json")
        entries = weight.get("body-weight", [])
        if entries:
            points.append(HealthMetricPoint("fitbit", WEIGHT_KG, float(entries[-1]["value"]), "kg", d))
    except Exception as e:
        log.warning("Fitbit weight: %s", e)

    count = persist(db, points)
    _update_sync(db, "fitbit", "ok", count)
    return points


# ── Integration class (auto-discovered by sync.py) ────────────────────────────

from backend.services.health_integrations.base import EnvField, HealthIntegration, IntegrationManifest  # noqa: E402


class FitbitIntegration(HealthIntegration):
    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            id="fitbit", name="Fitbit",
            description="Steps, sleep, heart rate, SpO2, HRV, breathing rate",
            auth_type="oauth",
            env_fields=[
                EnvField("FITBIT_CLIENT_ID",     "Client ID",     placeholder="your-fitbit-client-id"),
                EnvField("FITBIT_CLIENT_SECRET", "Client Secret", secret=True, placeholder="your-fitbit-client-secret"),
            ],
            help_text=(
                "1. Go to dev.fitbit.com → Register an App (Personal)\n"
                "2. Set OAuth 2.0 redirect URI to:\n"
                "   http://127.0.0.1:8899/api/health/oauth/callback\n"
                "3. Copy Client ID and Secret, then click Connect"
            ),
            help_url="https://dev.fitbit.com/apps/new",
        )

    def is_configured(self) -> bool:
        return fitbit_is_configured()

    async def sync(self, db, target_date=None):
        return await fitbit_sync(db, target_date)

    async def oauth_url(self, redirect_uri):
        return await fitbit_oauth_url(redirect_uri)

    async def exchange_code(self, code, redirect_uri):
        return await fitbit_exchange_code(code, redirect_uri)
