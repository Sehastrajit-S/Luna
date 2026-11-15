# Backward-compat shim — all logic lives in backend.services.health_integrations package
from backend.services.health_integrations import *  # noqa: F401, F403
from backend.services.health_integrations import (
    HealthMetricPoint, HealthIntegrationError, METRIC_UNITS,
    STEPS, DISTANCE_KM, CALORIES, HEART_RATE, RESTING_HR, HRV,
    SLEEP_DURATION, SLEEP_DEEP, SLEEP_REM, SLEEP_LIGHT, SLEEP_AWAKE,
    SLEEP_SCORE, BLOOD_OXYGEN, WEIGHT_KG, BMI, BODY_FAT_PCT,
    BP_SYSTOLIC, BP_DIASTOLIC, STRESS_SCORE, READINESS_SCORE,
    VO2_MAX, RESPIRATORY_RATE, SKIN_TEMP, ACTIVE_MINUTES, WORKOUT,
    persist, get_sync_status, query_metrics, daily_summary,
    fitbit_is_configured, fitbit_oauth_url, fitbit_exchange_code, fitbit_sync,
    google_fit_is_configured, google_fit_oauth_url, google_fit_exchange_code, google_fit_sync,
    oura_is_configured, oura_sync,
    withings_is_configured, withings_oauth_url, withings_exchange_code, withings_sync,
    garmin_is_configured, garmin_sync,
    parse_apple_health_export, parse_samsung_health_export,
    PLATFORM_SYNC, PLATFORM_CONFIGURED, PLATFORM_OAUTH,
    sync_all, integration_status,
)
