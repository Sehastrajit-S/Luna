"""Health metric type constants and data model."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

# ── Metric type constants ──────────────────────────────────────────────────

STEPS            = "steps"
DISTANCE_KM      = "distance_km"
CALORIES         = "calories"
HEART_RATE       = "heart_rate"
RESTING_HR       = "resting_heart_rate"
HRV              = "hrv"
SLEEP_DURATION   = "sleep_duration_min"
SLEEP_DEEP       = "sleep_deep_min"
SLEEP_REM        = "sleep_rem_min"
SLEEP_LIGHT      = "sleep_light_min"
SLEEP_AWAKE      = "sleep_awake_min"
SLEEP_SCORE      = "sleep_score"
BLOOD_OXYGEN     = "blood_oxygen_pct"
WEIGHT_KG        = "weight_kg"
BMI              = "bmi"
BODY_FAT_PCT     = "body_fat_pct"
BP_SYSTOLIC      = "blood_pressure_systolic"
BP_DIASTOLIC     = "blood_pressure_diastolic"
STRESS_SCORE     = "stress_score"
READINESS_SCORE  = "readiness_score"
VO2_MAX          = "vo2_max"
RESPIRATORY_RATE = "respiratory_rate"
SKIN_TEMP        = "skin_temp_c"
ACTIVE_MINUTES   = "active_minutes"
WORKOUT          = "workout"

METRIC_UNITS: dict[str, str] = {
    STEPS:            "steps",
    DISTANCE_KM:      "km",
    CALORIES:         "kcal",
    HEART_RATE:       "bpm",
    RESTING_HR:       "bpm",
    HRV:              "ms",
    SLEEP_DURATION:   "min",
    SLEEP_DEEP:       "min",
    SLEEP_REM:        "min",
    SLEEP_LIGHT:      "min",
    SLEEP_AWAKE:      "min",
    SLEEP_SCORE:      "score",
    BLOOD_OXYGEN:     "%",
    WEIGHT_KG:        "kg",
    BMI:              "kg/m2",
    BODY_FAT_PCT:     "%",
    BP_SYSTOLIC:      "mmHg",
    BP_DIASTOLIC:     "mmHg",
    STRESS_SCORE:     "score",
    READINESS_SCORE:  "score",
    VO2_MAX:          "mL/kg/min",
    RESPIRATORY_RATE: "rpm",
    SKIN_TEMP:        "°C",
    ACTIVE_MINUTES:   "min",
    WORKOUT:          "",
}


@dataclass
class HealthMetricPoint:
    platform:    str
    metric_type: str
    value:       float
    unit:        str
    date_str:    str                          # YYYY-MM-DD
    timestamp:   Optional[datetime] = None   # intra-day precision
    raw:         dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        if self.timestamp:
            d["timestamp"] = self.timestamp.isoformat()
        d.pop("raw", None)
        return d


class HealthIntegrationError(Exception):
    pass
