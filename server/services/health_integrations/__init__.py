"""Health platform integration service."""
from backend.services.health_integrations.models import (
    ACTIVE_MINUTES, BLOOD_OXYGEN, BMI, BODY_FAT_PCT, BP_DIASTOLIC,
    BP_SYSTOLIC, CALORIES, DISTANCE_KM, HEART_RATE, HRV, METRIC_UNITS,
    READINESS_SCORE, RESTING_HR, RESPIRATORY_RATE, SKIN_TEMP, SLEEP_AWAKE,
    SLEEP_DEEP, SLEEP_DURATION, SLEEP_LIGHT, SLEEP_REM, SLEEP_SCORE,
    STEPS, STRESS_SCORE, VO2_MAX, WEIGHT_KG, WORKOUT,
    HealthIntegrationError, HealthMetricPoint,
)
from backend.services.health_integrations.db import (
    daily_summary, get_sync_status, persist, query_metrics,
)
from backend.services.health_integrations.webhooks import (
    parse_apple_health_export, parse_samsung_health_export,
)
from backend.services.health_integrations.sync import (
    PLATFORM_CONFIGURED, PLATFORM_OAUTH, PLATFORM_SYNC,
    integration_status, sync_all,
)

__all__ = [
    "HealthMetricPoint", "HealthIntegrationError", "METRIC_UNITS",
    "STEPS", "DISTANCE_KM", "CALORIES", "HEART_RATE", "RESTING_HR", "HRV",
    "SLEEP_DURATION", "SLEEP_DEEP", "SLEEP_REM", "SLEEP_LIGHT", "SLEEP_AWAKE",
    "SLEEP_SCORE", "BLOOD_OXYGEN", "WEIGHT_KG", "BMI", "BODY_FAT_PCT",
    "BP_SYSTOLIC", "BP_DIASTOLIC", "STRESS_SCORE", "READINESS_SCORE",
    "VO2_MAX", "RESPIRATORY_RATE", "SKIN_TEMP", "ACTIVE_MINUTES", "WORKOUT",
    "persist", "get_sync_status", "query_metrics", "daily_summary",
    "parse_apple_health_export", "parse_samsung_health_export",
    "PLATFORM_SYNC", "PLATFORM_CONFIGURED", "PLATFORM_OAUTH",
    "sync_all", "integration_status",
]
