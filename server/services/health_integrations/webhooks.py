"""Apple Health and Samsung Health webhook parsers."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.services.health_integrations.db import _update_sync, persist
from backend.services.health_integrations.models import (
    ACTIVE_MINUTES, BLOOD_OXYGEN, BMI, BODY_FAT_PCT, BP_DIASTOLIC,
    BP_SYSTOLIC, CALORIES, DISTANCE_KM, HEART_RATE, HRV, RESTING_HR,
    RESPIRATORY_RATE, SLEEP_DURATION, STEPS, VO2_MAX, WEIGHT_KG,
    HealthMetricPoint,
)

_APPLE_METRIC_MAP = {
    "step_count":                   (STEPS,            "steps"),
    "steps":                        (STEPS,            "steps"),
    "heart_rate":                   (HEART_RATE,       "bpm"),
    "resting_heart_rate":           (RESTING_HR,       "bpm"),
    "heart_rate_variability_sdnn":  (HRV,              "ms"),
    "hrv":                          (HRV,              "ms"),
    "active_energy_burned":         (CALORIES,         "kcal"),
    "distance_walking_running":     (DISTANCE_KM,      "km"),
    "body_mass":                    (WEIGHT_KG,        "kg"),
    "body_mass_index":              (BMI,              "kg/m2"),
    "body_fat_percentage":          (BODY_FAT_PCT,     "%"),
    "oxygen_saturation":            (BLOOD_OXYGEN,     "%"),
    "blood_pressure_systolic":      (BP_SYSTOLIC,      "mmHg"),
    "blood_pressure_diastolic":     (BP_DIASTOLIC,     "mmHg"),
    "respiratory_rate":             (RESPIRATORY_RATE, "rpm"),
    "vo2_max":                      (VO2_MAX,          "mL/kg/min"),
    "sleep_analysis":               (SLEEP_DURATION,   "min"),
    "mindful_minutes":              (ACTIVE_MINUTES,   "min"),
}


def parse_apple_health_export(payload: dict, db: Session) -> list[HealthMetricPoint]:
    points: list[HealthMetricPoint] = []
    metrics_list = payload.get("data", {}).get("metrics", payload.get("metrics", []))

    for metric in metrics_list:
        raw_name = metric.get("name", "").lower().replace(" ", "_")
        if raw_name not in _APPLE_METRIC_MAP:
            continue
        m_type, m_unit = _APPLE_METRIC_MAP[raw_name]
        for dp in metric.get("data", []):
            qty      = dp.get("qty") or dp.get("value") or dp.get("Qty")
            date_raw = dp.get("date") or dp.get("startDate") or dp.get("Date")
            if qty is None or not date_raw:
                continue
            try:
                date_str = str(date_raw)[:10]
                ts: Optional[datetime] = datetime.fromisoformat(date_raw.replace("Z", "+00:00")) if "T" in date_raw else None
                unit_raw = metric.get("units", "")
                val = float(qty)
                if m_type == DISTANCE_KM and "mi" in unit_raw.lower():
                    val *= 1.60934
                points.append(HealthMetricPoint("apple", m_type, val, m_unit, date_str, ts))
            except Exception:
                continue

    if points:
        persist(db, points)
        _update_sync(db, "apple", "ok", len(points))
    return points


_SAMSUNG_METRIC_MAP = {
    "step_count":      (STEPS,            "steps"),
    "stepCount":       (STEPS,            "steps"),
    "heart_rate":      (HEART_RATE,       "bpm"),
    "heartRate":       (HEART_RATE,       "bpm"),
    "calories":        (CALORIES,         "kcal"),
    "caloriesBurned":  (CALORIES,         "kcal"),
    "distance":        (DISTANCE_KM,      "km"),
    "sleepDuration":   (SLEEP_DURATION,   "min"),
    "weight":          (WEIGHT_KG,        "kg"),
    "bloodOxygen":     (BLOOD_OXYGEN,     "%"),
    "stressScore":     (ACTIVE_MINUTES,   "score"),
    "vo2Max":          (VO2_MAX,          "mL/kg/min"),
}


def parse_samsung_health_export(payload: dict, db: Session) -> list[HealthMetricPoint]:
    metrics_list = payload.get("data", {}).get("metrics", payload.get("metrics", []))
    if metrics_list:
        return parse_apple_health_export(payload, db)

    points: list[HealthMetricPoint] = []
    for key, (m_type, m_unit) in _SAMSUNG_METRIC_MAP.items():
        if key not in payload:
            continue
        entries = payload[key]
        if not isinstance(entries, list):
            entries = [entries]
        for entry in entries:
            val      = entry.get("value") or entry.get("count") or entry.get("amount")
            date_raw = entry.get("start_time") or entry.get("date") or entry.get("timestamp")
            if val is None or not date_raw:
                continue
            try:
                date_str = str(date_raw)[:10]
                ts: Optional[datetime] = None
                if "T" in str(date_raw):
                    ts = datetime.fromisoformat(str(date_raw).replace("Z", "+00:00"))
                points.append(HealthMetricPoint("samsung", m_type, float(val), m_unit, date_str, ts))
            except Exception:
                continue

    if points:
        persist(db, points)
        _update_sync(db, "samsung", "ok", len(points))
    return points
