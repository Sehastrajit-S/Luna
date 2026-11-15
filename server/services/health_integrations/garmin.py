"""Garmin Connect sync via the garth library."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.health_integrations.db import _update_sync, persist
from backend.services.health_integrations.models import (
    BLOOD_OXYGEN, CALORIES, DISTANCE_KM, HRV, READINESS_SCORE,
    RESTING_HR, SLEEP_AWAKE, SLEEP_DEEP, SLEEP_DURATION, SLEEP_LIGHT,
    SLEEP_REM, STEPS, STRESS_SCORE,
    HealthIntegrationError, HealthMetricPoint,
)

log = logging.getLogger(__name__)


def garmin_is_configured() -> bool:
    return bool(settings.garmin_email and settings.garmin_password)


async def garmin_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    if not garmin_is_configured():
        raise HealthIntegrationError("Garmin not configured — set garmin_email, garmin_password in .env")
    try:
        import garth  # type: ignore
    except ImportError:
        raise HealthIntegrationError("garth library not installed — run: pip install garth")

    d      = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []

    try:
        garth.login(settings.garmin_email, settings.garmin_password)

        stats = garth.connectapi(f"/wellness-service/wellness/dailySummaryChart/{d}")
        if isinstance(stats, dict):
            if "totalSteps"          in stats: points.append(HealthMetricPoint("garmin", STEPS,        float(stats["totalSteps"]),                 "steps", d))
            if "totalKilocalories"   in stats: points.append(HealthMetricPoint("garmin", CALORIES,     float(stats["totalKilocalories"]),          "kcal",  d))
            if "totalDistanceMeters" in stats: points.append(HealthMetricPoint("garmin", DISTANCE_KM,  float(stats["totalDistanceMeters"]) / 1000, "km",    d))
            if "restingHeartRate"    in stats: points.append(HealthMetricPoint("garmin", RESTING_HR,   float(stats["restingHeartRate"]),           "bpm",   d))
            if "averageStressLevel"  in stats and stats["averageStressLevel"] >= 0:
                points.append(HealthMetricPoint("garmin", STRESS_SCORE, float(stats["averageStressLevel"]), "score", d))
            if "bodyBattery" in stats:
                battery = stats["bodyBattery"]
                if isinstance(battery, list) and battery:
                    latest = battery[-1].get("value", battery[-1])
                    if isinstance(latest, (int, float)):
                        points.append(HealthMetricPoint("garmin", READINESS_SCORE, float(latest), "score", d))

        sleep_data = garth.connectapi(f"/wellness-service/wellness/dailySleepData/{d}")
        if isinstance(sleep_data, dict):
            summary = sleep_data.get("dailySleepDTO", {})
            if "sleepTimeSeconds"  in summary: points.append(HealthMetricPoint("garmin", SLEEP_DURATION, float(summary["sleepTimeSeconds"])  / 60, "min", d))
            if "deepSleepSeconds"  in summary: points.append(HealthMetricPoint("garmin", SLEEP_DEEP,     float(summary["deepSleepSeconds"])   / 60, "min", d))
            if "remSleepSeconds"   in summary: points.append(HealthMetricPoint("garmin", SLEEP_REM,      float(summary["remSleepSeconds"])    / 60, "min", d))
            if "lightSleepSeconds" in summary: points.append(HealthMetricPoint("garmin", SLEEP_LIGHT,    float(summary["lightSleepSeconds"])  / 60, "min", d))
            if "awakeSleepSeconds" in summary: points.append(HealthMetricPoint("garmin", SLEEP_AWAKE,    float(summary["awakeSleepSeconds"])  / 60, "min", d))
            if "averageSpO2"       in summary: points.append(HealthMetricPoint("garmin", BLOOD_OXYGEN,   float(summary["averageSpO2"]),            "%",  d))
            if "avgSleepStress"    in summary and summary["avgSleepStress"] > 0:
                points.append(HealthMetricPoint("garmin", HRV, float(summary["avgSleepStress"]), "ms", d))

        hrv_data = garth.connectapi(f"/hrv-service/hrv/{d}")
        if isinstance(hrv_data, dict):
            hrv_val = hrv_data.get("lastNight", {}).get("avg5MinHrv")
            if hrv_val:
                points.append(HealthMetricPoint("garmin", HRV, float(hrv_val), "ms", d))

    except HealthIntegrationError:
        raise
    except Exception as e:
        _update_sync(db, "garmin", "error", 0, str(e))
        raise HealthIntegrationError(f"Garmin sync failed: {e}") from e

    count = persist(db, points)
    _update_sync(db, "garmin", "ok", count)
    return points


# ── Integration class (auto-discovered by sync.py) ────────────────────────────

from backend.services.health_integrations.base import EnvField, HealthIntegration, IntegrationManifest  # noqa: E402


class GarminIntegration(HealthIntegration):
    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            id="garmin", name="Garmin",
            description="GPS, steps, heart rate, sleep, body battery",
            auth_type="credentials",
            env_fields=[
                EnvField("GARMIN_EMAIL",    "Garmin Email",    placeholder="you@example.com"),
                EnvField("GARMIN_PASSWORD", "Garmin Password", secret=True, placeholder="your password"),
            ],
            help_text="Enter your Garmin Connect account credentials. Luna uses garth to fetch activity data directly.",
            help_url="https://connect.garmin.com",
        )

    def is_configured(self) -> bool:
        return garmin_is_configured()

    async def sync(self, db, target_date=None):
        return await garmin_sync(db, target_date)
