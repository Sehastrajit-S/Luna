"""Oura Ring personal API token sync."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.health_integrations.db import _update_sync, persist
from backend.services.health_integrations.models import (
    ACTIVE_MINUTES, CALORIES, DISTANCE_KM, HEART_RATE, HRV,
    READINESS_SCORE, RESTING_HR, RESPIRATORY_RATE, SLEEP_AWAKE,
    SLEEP_DEEP, SLEEP_DURATION, SLEEP_LIGHT, SLEEP_REM, STEPS, STRESS_SCORE,
    HealthIntegrationError, HealthMetricPoint,
)
from backend.services.health_integrations.oauth import _get

log = logging.getLogger(__name__)

OURA_BASE = "https://api.ouraring.com/v2/usercollection"


def oura_is_configured() -> bool:
    return bool(settings.oura_api_key)


async def oura_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    if not oura_is_configured():
        raise HealthIntegrationError("Oura not configured — set oura_api_key in .env")
    token  = settings.oura_api_key
    d      = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []
    params = {"start_date": d, "end_date": d}

    async def _oura_get(endpoint: str) -> dict:
        return await _get(f"{OURA_BASE}/{endpoint}", token, params)

    try:
        act = await _oura_get("daily_activity")
        for entry in act.get("data", []):
            if entry.get("day") == d:
                if "steps"                     in entry: points.append(HealthMetricPoint("oura", STEPS,         float(entry["steps"]),                          "steps", d))
                if "active_calories"           in entry: points.append(HealthMetricPoint("oura", CALORIES,      float(entry["active_calories"]),                "kcal",  d))
                if "equivalent_walking_distance" in entry:
                    points.append(HealthMetricPoint("oura", DISTANCE_KM, float(entry["equivalent_walking_distance"]) / 1000, "km", d))
                if "meet_daily_targets"        in entry:
                    points.append(HealthMetricPoint("oura", ACTIVE_MINUTES, float(entry.get("high_activity_time", 0)) / 60, "min", d))
    except Exception as e:
        log.warning("Oura daily_activity: %s", e)

    try:
        sleep = await _oura_get("sleep")
        for entry in sleep.get("data", []):
            if entry.get("day") == d:
                total = entry.get("total_sleep_duration", 0)
                points.append(HealthMetricPoint("oura", SLEEP_DURATION, float(total) / 60, "min", d))
                if "deep_sleep_duration"   in entry: points.append(HealthMetricPoint("oura", SLEEP_DEEP,  float(entry["deep_sleep_duration"])  / 60, "min", d))
                if "rem_sleep_duration"    in entry: points.append(HealthMetricPoint("oura", SLEEP_REM,   float(entry["rem_sleep_duration"])   / 60, "min", d))
                if "light_sleep_duration"  in entry: points.append(HealthMetricPoint("oura", SLEEP_LIGHT, float(entry["light_sleep_duration"]) / 60, "min", d))
                if "awake_time"            in entry: points.append(HealthMetricPoint("oura", SLEEP_AWAKE, float(entry["awake_time"])           / 60, "min", d))
                if "average_hrv"           in entry: points.append(HealthMetricPoint("oura", HRV,         float(entry["average_hrv"]),               "ms",  d))
                if "lowest_heart_rate"     in entry: points.append(HealthMetricPoint("oura", RESTING_HR,  float(entry["lowest_heart_rate"]),         "bpm", d))
                if "average_breathing_rate" in entry: points.append(HealthMetricPoint("oura", RESPIRATORY_RATE, float(entry["average_breathing_rate"]), "rpm", d))
    except Exception as e:
        log.warning("Oura sleep: %s", e)

    try:
        readiness = await _oura_get("daily_readiness")
        for entry in readiness.get("data", []):
            if entry.get("day") == d and "score" in entry:
                points.append(HealthMetricPoint("oura", READINESS_SCORE, float(entry["score"]), "score", d))
    except Exception as e:
        log.warning("Oura readiness: %s", e)

    try:
        stress = await _oura_get("daily_stress")
        for entry in stress.get("data", []):
            if entry.get("day") == d and "stress_high" in entry:
                points.append(HealthMetricPoint("oura", STRESS_SCORE, float(entry["stress_high"]), "score", d))
    except Exception as e:
        log.warning("Oura stress: %s", e)

    try:
        hr = await _oura_get("heartrate")
        today_hrs = [e["bpm"] for e in hr.get("data", []) if e.get("timestamp", "").startswith(d)]
        if today_hrs:
            points.append(HealthMetricPoint("oura", HEART_RATE, float(sum(today_hrs) / len(today_hrs)), "bpm", d))
    except Exception as e:
        log.warning("Oura heart rate: %s", e)

    count = persist(db, points)
    _update_sync(db, "oura", "ok", count)
    return points


# ── Integration class (auto-discovered by sync.py) ────────────────────────────

from backend.services.health_integrations.base import EnvField, HealthIntegration, IntegrationManifest  # noqa: E402


class OuraIntegration(HealthIntegration):
    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            id="oura", name="Oura Ring",
            description="Sleep, readiness, HRV, activity, stress",
            auth_type="apikey",
            env_fields=[
                EnvField("OURA_API_KEY", "Personal Access Token", secret=True, placeholder="your-oura-token"),
            ],
            help_text=(
                "1. Go to cloud.ouraring.com/user/settings\n"
                "2. Open the Personal Access Tokens section\n"
                "3. Generate a new token and paste it below"
            ),
            help_url="https://cloud.ouraring.com/user/settings",
        )

    def is_configured(self) -> bool:
        return oura_is_configured()

    async def sync(self, db, target_date=None):
        return await oura_sync(db, target_date)
